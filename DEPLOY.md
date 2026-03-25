# Guia de Deploy Completo

## Resumo da arquitetura

| Componente | Serviço   | URL (exemplo)                    |
|------------|-----------|-----------------------------------|
| **Banco de dados** | Supabase  | `postgresql://...@pooler.supabase.com:6543/postgres` |
| **Backend**        | Render    | `https://seu-projeto.onrender.com` |
| **Frontend**       | Vercel    | `https://seu-projeto.vercel.app`     |

---

## Fluxo de deploy (ordem correta)

As variáveis de ambiente dependem umas das outras. Siga **exatamente** esta ordem:

| Etapa | O que fazer | Variáveis que você já tem |
|-------|--------------|---------------------------|
| **1** | [Supabase](#1-supabase---banco-de-dados) | `DATABASE_URL` |
| **2** | [Render – 1º deploy](#3-render---backend) | `DATABASE_URL`, `HF_TOKEN`, `GOOGLE_CREDENTIALS_JSON` |
| **3** | Obter URL do Render e [Google Cloud](#2-google-cloud---gmail-oauth) | `API_BASE_URL` (URL do Render) |
| **4** | [Vercel – frontend](#4-vercel---frontend) | `NEXT_PUBLIC_API_URL` = URL do Render |
| **5** | Atualizar Render com URL do Vercel | `FRONTEND_URL` (URL do Vercel) |
| **6** | [Testar](#5-testar-o-deploy) | — |

---

## 1. Supabase – Banco de dados

### 1.1 Criar projeto

1. Acesse [supabase.com](https://supabase.com) e crie uma conta (ou faça login)
2. Clique em **New Project**
3. Preencha:
   - **Name**: `email-classifier` (ou outro nome)
   - **Database Password**: crie uma senha forte e **guarde**
   - **Region**: escolha a mais próxima (ex: South America)
4. Clique em **Create new project** e aguarde a criação

### 1.2 Obter a connection string

1. No menu lateral, vá em **Project Settings** (ícone de engrenagem)
2. Clique em **Database**
3. Em **Connection string**, selecione **URI**
4. Copie a URL (formato: `postgresql://postgres.[PROJECT_REF]:[SENHA]@aws-0-[REGION].pooler.supabase.com:6543/postgres`)
5. **Importante**: Supabase usa a porta **6543** (pooler) para conexões externas. Use essa URL.

### 1.3 Formato para o backend

O backend usa `psycopg` (versão 3). A URL do Supabase já vem no formato correto. Exemplo:

```
postgresql://postgres.[PROJECT_REF]:[SUA_SENHA]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres
```

Guarde essa URL – você usará como `DATABASE_URL` no Render.

### 1.4 Schema do banco (dev = prod)

Em cada **subida do backend** (Render ou `uvicorn` local com PostgreSQL), o app executa:

1. `create_all` — cria tabelas que ainda não existem  
2. Garantias legadas de colunas (ex.: `gmail_account_email` em bases antigas)  
3. **Alembic `upgrade head`** — aplica revisões em `backend/migrations/versions/`

Assim produção recebe as mesmas revisões que o repositório assim que o novo código sobe. **Conteúdo dos dados** (linhas nas tabelas) não é copiado entre ambientes; o que fica alinhado é **estrutura e versão de migração**.

**Regras para dev e prod permanecerem iguais:**

| Regra | Motivo |
|--------|--------|
| Desenvolvimento diário com **PostgreSQL** local (`docker compose up` + `DATABASE_URL` no `backend/.env`) | Mesmo fluxo de startup que o Render (`create_all` + Alembic). |
| **Não** alterar schema só no Supabase/DBeaver (`ALTER` manual em prod) | O código não fica rastreado; no próximo ambiente o schema diverge. |
| Qualquer mudança em `app/models.py` → **nova revisão Alembic** no mesmo PR/commit | Uma única fonte da verdade no Git. |
| Antes de merge/deploy: `make db-upgrade` no Postgres local e smoke na API | Confirma que a revisão aplica sem erro. |
| Opcional: `make db-migration-status` | `current` deve coincidir com `heads` após o upgrade. |

No repositório, `make db-check-alembic` (e o workflow **Backend schema** no GitHub) garantem **um único head** do Alembic — evita duas linhas de migração divergentes.

**Nova alteração de schema:** no diretório `backend/`, `alembic revision -m "descrição"`, edite o arquivo em `migrations/versions/`, teste com `make db-upgrade`, faça commit e deploy. O Render aplica `upgrade head` no startup. *(A pasta chama-se `migrations` — e não `alembic` — para não conflitar com o pacote Python `alembic` no `import`.)*

---

## 2. Google Cloud – Gmail OAuth

**Faça isso após o 1º deploy no Render** (quando você tiver a URL do backend).

### 2.1 Adicionar URI de produção

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Selecione o projeto do Email Classifier
3. Vá em **APIs e Serviços** → **Credenciais**
4. Clique no **ID do cliente OAuth** que você usa
5. Em **URIs de redirecionamento autorizados**, adicione:
   ```
   https://SUA-URL-RENDER.onrender.com/api/auth/gmail/callback
   ```
   *(Use a URL real do backend no Render – obtida no passo 3.3)*

6. Clique em **Salvar**

---

## 3. Render – Backend

### 3.1 Criar serviço (manual ou Blueprint)

**Opção A – Manual:**
1. Clique em **New** → **Web Service**
2. Conecte o repositório e selecione o projeto
3. Configure:
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt` *(apenas o comando, sem prefixos)*
   - **Start Command**: `sh scripts/start.sh` *(não use `python scripts/start.sh` – é um script shell)*

**Opção B – Blueprint:** New → Blueprint, conecte o repo, Apply (usa `render.yaml`).

### 3.2 Variáveis para o 1º deploy

No **1º deploy** você ainda **não tem** a URL do Vercel. Adicione apenas:

| Variável | Valor | Quando preencher |
|----------|-------|------------------|
| `DATABASE_URL` | URL do Supabase (pooler, porta 6543) | Agora |
| `HF_TOKEN` | Token do [Hugging Face](https://huggingface.co/settings/tokens) | Agora |
| `GOOGLE_CREDENTIALS_JSON` | Conteúdo completo do `credentials.json` | Agora |
| `API_BASE_URL` | *(deixe em branco no 1º deploy)* | Após o deploy (3.3) |
| `FRONTEND_URL` | *(deixe em branco no 1º deploy)* | Após o deploy do Vercel (4.5) |
| `USER_NAME` | ⚪ Opcional | — |
| `DISABLE_JOB_SCHEDULER` | ⚪ `1` para desabilitar job diário | — |

> O backend usa `API_BASE_URL` default `http://localhost:8000` e `FRONTEND_URL` default `http://localhost:3000` se não definidos. O Gmail OAuth **só funcionará** depois de atualizar com as URLs reais.

### 3.3 Após o 1º deploy – obter URL e atualizar

1. Aguarde o deploy terminar
2. No Render, copie a URL do serviço (ex: `https://email-classifier.onrender.com`)
3. Em **Environment**, adicione/atualize:
   - `API_BASE_URL` = `https://sua-url.onrender.com` (sem barra no final)
4. Clique em **Save Changes** – o Render fará redeploy
5. Vá ao [Google Cloud](#2-google-cloud---gmail-oauth) e adicione a URI de callback:
   ```
   https://sua-url.onrender.com/api/auth/gmail/callback
   ```

### 3.4 Testar o backend

- Acesse `https://sua-url.onrender.com/health` → deve retornar `{"status":"healthy"}`

### 3.5 Plano Free e cold start

No plano **Free**, o serviço entra em sleep após ~15 min de inatividade. A primeira requisição após o sleep pode levar 30–60 segundos (cold start). Para evitar isso, use o plano **Starter** ($7/mês).

---

## 4. Vercel – Frontend

**Faça isso após o backend estar no ar** (você precisa da URL do Render para `NEXT_PUBLIC_API_URL`).

### 4.1 Criar projeto

1. Acesse [vercel.com](https://vercel.com) e crie uma conta (ou faça login com GitHub)
2. Clique em **Add New** → **Project**
3. Importe o repositório do GitHub
4. Selecione o repositório do projeto

### 4.2 Configurar o build

1. **Root Directory**: clique em **Edit** e defina `frontend`
2. **Framework Preset**: Next.js (deve ser detectado automaticamente)
3. **Build Command**: deixe o padrão (`next build`)
4. **Output Directory**: deixe o padrão

### 4.3 Variáveis de ambiente

Em **Environment Variables**, adicione **antes** do deploy:

| Variável | Valor | Ambiente |
|----------|-------|----------|
| `NEXT_PUBLIC_API_URL` | `https://SUA-URL-RENDER.onrender.com` | Production, Preview, Development |

Use a URL do backend no Render (sem barra no final). Sem isso, o frontend não conseguirá chamar a API.

### 4.4 Deploy

1. Clique em **Deploy**
2. Aguarde o build
3. Copie a URL do projeto (ex: `https://email-classifier.vercel.app`)

### 4.5 Atualizar backend (obrigatório para Gmail)

No **Render**, vá em **Environment** e adicione/atualize:

| Variável | Valor |
|----------|-------|
| `FRONTEND_URL` | `https://sua-url.vercel.app` (URL do Vercel, sem barra no final) |

Clique em **Save Changes** – o Render fará redeploy. Sem isso, o redirect do Gmail OAuth não funcionará (o usuário seria redirecionado para localhost).

---

## 5. Testar o deploy

### 5.1 Health check

- Backend: `https://SUA-URL-RENDER.onrender.com/health`
- Deve retornar: `{"status":"healthy"}`

### 5.2 Frontend

1. Acesse a URL do Vercel
2. Teste a classificação de email (texto ou arquivo)
3. Conecte o Gmail (botão **Conectar Gmail**)
4. Autorize no Google e verifique se os emails aparecem

### 5.3 Gmail em produção

- **Tokens**: O `gmail_tokens.json` é efêmero no Render. A cada novo deploy, será necessário **reconectar o Gmail** uma vez.
- Para evitar isso no futuro, os tokens podem ser persistidos no banco (Supabase) – isso exigiria alteração no código.

---

## 6. Checklist final

- [ ] **1.** Supabase: projeto criado e `DATABASE_URL` obtida (pooler, porta 6543)
- [ ] **2.** Render: 1º deploy com `DATABASE_URL`, `HF_TOKEN`, `GOOGLE_CREDENTIALS_JSON`
- [ ] **3.** Render: `API_BASE_URL` atualizada com a URL do Render
- [ ] **4.** Google Cloud: URI de callback `https://SUA-URL.onrender.com/api/auth/gmail/callback`
- [ ] **5.** Vercel: deploy com `NEXT_PUBLIC_API_URL` = URL do Render
- [ ] **6.** Render: `FRONTEND_URL` atualizada com a URL do Vercel
- [ ] Teste: `/health` no backend
- [ ] Teste: classificação e conexão Gmail no frontend

---

## 7. CORS (opcional)

O backend está com `allow_origins=["*"]`. Para maior segurança em produção, restrinja ao domínio do frontend:

```python
# backend/app/main.py
allow_origins=[
    "https://seu-projeto.vercel.app",
    "https://seu-projeto-*.vercel.app",  # preview deployments
]
```

---

## 8. Custos estimados

| Serviço   | Plano   | Custo aproximado      |
|-----------|---------|------------------------|
| Supabase  | Free    | Grátis até 500 MB      |
| Render    | Free    | Grátis (com cold start) |
| Render    | Starter | $7/mês (sem sleep)     |
| Vercel    | Hobby   | Grátis                 |
| Hugging Face | Free | Grátis (com limites)   |

---

## 9. Troubleshooting

### Backend não inicia

- Verifique os logs no Render
- Confirme que `DATABASE_URL` está correta (porta 6543 para Supabase pooler)
- Confirme que `GOOGLE_CREDENTIALS_JSON` está como JSON válido

### Erro de CORS

- Verifique se `NEXT_PUBLIC_API_URL` no frontend está correta
- Confirme que `FRONTEND_URL` no backend está correta

### Gmail "redirect_uri_mismatch"

- Adicione exatamente a URL de callback no Google Cloud:
  `https://SUA-URL-RENDER.onrender.com/api/auth/gmail/callback`
- Sem barra no final, com `https://`

### Tabelas não existem

O backend cria as tabelas automaticamente no primeiro request (`init_db`). Se houver erro, verifique a conexão com o Supabase e as permissões do usuário.
