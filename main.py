from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3

app = FastAPI(title="Kanban API")

# Libera o acesso para o Frontend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Função auxiliar para conectar no banco
def get_db_connection():
    conn = sqlite3.connect('database.sqlite')
    conn.row_factory = sqlite3.Row # Permite acessar colunas pelo nome
    return conn

# Inicializa o banco e as tabelas
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (column_id) REFERENCES columns(id)
        )
    ''')
    
    # Insere colunas padrão se o banco estiver vazio
    count = conn.execute("SELECT COUNT(*) FROM columns").fetchone()[0]
    if count == 0:
        conn.execute("INSERT INTO columns (title) VALUES ('A Fazer')")
        conn.execute("INSERT INTO columns (title) VALUES ('Em Andamento')")
        conn.execute("INSERT INTO columns (title) VALUES ('Concluído')")
        conn.commit()
    conn.close()

# Roda a inicialização ao ligar o código
init_db()

# ==========================================
# MODELOS DE DADOS (Como recebemos os dados do frontend)
# ==========================================
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    column_id: int

class TaskMove(BaseModel):
    new_column_id: int

# ==========================================
# ROTAS (ENDPOINTS) DA NOSSA API
# ==========================================

# 1. Obter todo o Kanban (Colunas e tarefas)
@app.get("/kanban")
def get_kanban():
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT c.id as col_id, c.title as col_title, t.id as task_id, t.title as task_title, t.description 
        FROM columns c 
        LEFT JOIN tasks t ON c.id = t.column_id
    ''').fetchall()
    conn.close()
    
    kanban = {}
    for row in rows:
        col_id = row['col_id']
        if col_id not in kanban:
            kanban[col_id] = {"id": col_id, "title": row['col_title'], "tasks": []}
        
        if row['task_id']: # Se a coluna tiver uma tarefa, nós a adicionamos na lista
            kanban[col_id]["tasks"].append({
                "id": row['task_id'],
                "title": row['task_title'],
                "description": row['description']
            })
            
    return list(kanban.values())

# 2. Criar nova tarefa
@app.post("/tasks")
def create_task(task: TaskCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (title, description, column_id) VALUES (?, ?, ?)",
        (task.title, task.description, task.column_id)
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return {"id": task_id, "title": task.title, "description": task.description, "column_id": task.column_id}

# 3. Mover a tarefa de coluna (Drag and Drop do Frontend)
@app.put("/tasks/{task_id}/move")
def move_task(task_id: int, move: TaskMove):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET column_id = ? WHERE id = ?",
        (move.new_column_id, task_id)
    )
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    
    if changes == 0:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        
    return {"message": "Tarefa movida com sucesso"}

# 4. Deletar tarefa
@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    
    if changes == 0:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        
    return {"message": "Tarefa removida com sucesso"}
