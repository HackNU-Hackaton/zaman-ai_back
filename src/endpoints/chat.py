import io
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, File, UploadFile, HTTPException
from sqlalchemy import select, update, func, and_, insert
import math
from src.models.user import users_table
from src.models.chat import chat_messages_table
from src.utils.db import database
from src.utils.openai_client import client, assistant
from datetime import datetime
from typing import Optional
import tempfile
import os

from src.utils.transactions import get_user_transactions

router = APIRouter(
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)


@router.post("/chat/voice")
async def send_voice(file: UploadFile = File(...)):
    """
    Accepts an uploaded audio file and transcribes it using OpenAI's GPT-4o Transcription model.
    """

    tmp_path = None
    try:
        # Save uploaded file to a temporary location
        suffix = os.path.splitext(file.filename or "")[1] or ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # Open and transcribe
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.translations.create(
                model="whisper-1",
                file=audio_file,
                prompt="Ответь мне на русском языке"
            )

        return {"text": transcription.text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    finally:
        # Cleanup: remove the temp file
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

@router.get("/history/{user_id}")
async def get_history(
    user_id: int,
    after: Optional[str] = Query(None, description="Cursor ID of last message from previous page"),
    limit: int = Query(20, ge=1, le=100, description="Number of messages to fetch per page"),
    query: Optional[str] = Query(None, description="Optional text search within messages"),
):
    """
    Retrieve chat history for a given user using cursor-based pagination.

    - Fetches messages from OpenAI thread.
    - Uses `after` cursor for pagination (use message ID of the last message).
    - Optionally filters results by text content.
    """
    # Find user in DB
    user = await database.fetch_one(select(users_table).where(users_table.c.id == user_id))
    if not user:
        return {"error": "Invalid user ID"}

    user = dict(user)
    thread_id = user.get("thread_id")
    if not thread_id:
        return {
            "messages": [],
            "has_more": False,
            "next_cursor": None,
            "total_fetched": 0,
        }

    try:
        # Fetch from OpenAI thread with cursor-based pagination
        response = client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",       # newest first
            limit=limit,
            after=after,        # cursor for pagination
        )

        messages = []
        for msg in response.data:
            text_content = ""
            if msg.content and isinstance(msg.content, list):
                for block in msg.content:
                    if hasattr(block, "text") and hasattr(block.text, "value"):
                        text_content += block.text.value

            created_dt = (
                datetime.fromtimestamp(msg.created_at).isoformat()
                if msg.created_at
                else None
            )

            messages.append({
                "id": msg.id,
                "role": msg.role,
                "message": text_content,
                "created_at": created_dt,
                "is_active": True,
            })

        # Optional local filtering
        if query:
            messages = [m for m in messages if query.lower() in m["message"].lower()]

        # Return cursor info
        next_cursor = None
        if response.has_more and len(messages) > 0:
            next_cursor = messages[-1]["id"]  # the last message on this page

        return {
            "messages": messages,
            "has_more": response.has_more,
            "next_cursor": next_cursor,
            "total_fetched": len(messages),
        }

    except Exception as e:
        return {
            "messages": [],
            "has_more": False,
            "next_cursor": None,
            "total_fetched": 0,
        }

@router.websocket("/ws/chat/{user_id}")
async def chat_websocket(websocket: WebSocket, user_id: int):
    """
    WebSocket endpoint that streams assistant responses like ChatGPT.
    Message protocol:
      {"type": "system", "value": "START"}
      {"type": "word", "value": "Hello"}
      {"type": "word", "value": "world!"}
      {"type": "system", "value": "END"}
    On error:
      {"type": "error", "value": "Invalid ID"}
    """

    await websocket.accept()

    try:
        # Find user
        query = select(users_table).where(users_table.c.id == user_id)
        user = await database.fetch_one(query)

        if not user:
            await websocket.send_json({"type": "error", "value": "Invalid ID"})
            await websocket.send_json({"type": "system", "value": "END"})
            await websocket.close()
            return

        user = dict(user)

        # Get or create thread
        if user.get("thread_id"):
            thread = client.beta.threads.retrieve(user["thread_id"])
            transactions_file_id = user.get("transactions_file_id")
        else:
            transactions = get_user_transactions(user_id)

            if transactions:
                transactions_file = client.files.create(
                    file=io.BytesIO(json.dumps(transactions).encode('utf-8')),
                    purpose='assistants',
                )
                transactions_file_id = transactions_file.id

                type_message = ''

                if user['type_id'] == 1:
                    type_message = '[RINAT] Этот пользователь - физическое лицо. Ему нужно предлагать только продукты для физических лиц.'
                elif user['type_id'] == 2:
                    type_message = '[RINAT] Этот пользователь - юридическое лицо. Ему нужно предлагать только продукты для юридических лиц.'

                thread = client.beta.threads.create(messages=[
                        {
                            'role': 'user',
                            'content': type_message
                        },
                        {
                            'role': 'user',
                            'content': '''[RINAT] Я загружу JSON с банковскими транзакциями данного пользователя. Можешь использовать его для анализа доходов и расходов.
                            Файл содержит список JSON-объектов, у которых есть поля: 
                            `id` - идентификатор пользователя, 
                            `name` - имя пользователя,
                            `status` - откуда была произведена оплата,
                            `date` - дата транзакции,
                            `category` - категория транзакции,
                            `amount` - сумма транзакции,
                            `currency` - валюта,
                            `salary` - зарплата ползователя каждый месяц
                            `balance_left` - текущий баланс пользователя
                            ''',
                            # 'attachments': [
                            #     {'file_id': transactions_file.id, 'tools': [{'type': 'code_interpreter'}]}
                            # ]
                        }
                    ],tool_resources={
                        'code_interpreter': {
                            'file_ids': [transactions_file.id],
                        }
                    })
                # client.beta.threads.runs.create(
                #     thread_id=thread.id,
                #     assistant_id=assistant.id,
                #     instructions='Вот история транзакций данного пользователя в JSON формате. Используй её для анализа расходов и персонализированных предложений.',
                #     tool_resources={}
                # )
            else:
                thread = client.beta.threads.create()
                transactions_file_id = None
            await database.execute(
                update(users_table)
                .where(users_table.c.id == user_id)
                .values(thread_id=thread.id, transactions_file_id=transactions_file_id)
            )

        # Main chat loop
        while True:
            try:
                user_msg = await websocket.receive_text()

                # await database.execute(
                #     insert(chat_messages_table).values(
                #         user_id=user_id,
                #         role="user",
                #         message=user_msg,
                #         is_active=True,
                #         created_at=datetime.now(),
                #     )
                # )

                # Signal start of response
                await websocket.send_json({"type": "system", "value": "START"})

                # Add user message to thread
                client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=user_msg,
                    attachments=[
                        {'file_id': transactions_file_id, 'tools': [{'type': 'code_interpreter'}]}
                    ] if transactions_file_id else [],
                )

                # bot_reply = ""

                # Stream assistant reply
                with client.beta.threads.runs.stream(
                        thread_id=thread.id,
                        assistant_id=assistant.id,
                ) as stream:
                    message = ''
                    for event in stream:
                        if event.event == "thread.message.delta":
                            token = event.data.delta.content[0].text.value
                            # bot_reply += token
                            message += token
                            await websocket.send_json({"type": "word", "value": token})
                    # await websocket.send_text(message)

                # await database.execute(
                #     insert(chat_messages_table).values(
                #         user_id=user_id,
                #         role="bot",
                #         message=bot_reply,
                #         is_active=True,
                #         created_at=datetime.now(),
                #     )
                # )

                # End of response
                await websocket.send_json({"type": "system", "value": "END"})

            except WebSocketDisconnect:
                break
            except Exception as e:
                await websocket.send_json({"type": "error", "value": str(e)})
    except Exception as e:
        await websocket.send_json({"type": "error", "value": f"Server error: {str(e)}"})
        await websocket.close()
