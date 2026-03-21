# Guia de Deploy Completo

## Resumo da arquitetura

| Componente | Serviço   | URL (exemplo)                    |
|------------|-----------|-----------------------------------|
| **Banco de dados** | Supabase  | `postgresql://...@db.xxx.supabase.co:5432/postgres` |
| **Backend**        | Render    | `https://seu-projeto.onrender.com` |
| **Frontend**       | Vercel    | `https://seu-projeto.vercel.app`     |

---

## Ordem de execução

Siga os passos **nesta ordem**, pois cada etapa depende da anterior.

1. [Supabase](#1-supabase---banco-de-dados) – criar projeto e obter `DATABASE_URL`
2. [Google Cloud](#2-google-cloud---gmail-oauth) – configurar URIs de produção
3. [Render](#3-render---backend) – deploy do backend
4. [Vercel](#4-vercel---frontend) – deploy do frontend
5. [Testar](#5-testar-o-deploy) – validar integração

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

---

## 2. Google Cloud – Gmail OAuth

Antes do deploy, configure as URIs de redirecionamento para produção.

### 2.1 Adicionar URI de produção

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Selecione o projeto do Email Classifier
3. Vá em **APIs e Serviços** → **Credenciais**
4. Clique no **ID do cliente OAuth** que você usa
5. Em **URIs de redirecionamento autorizados**, adicione:
   ```
   https://SEU-BACKEND-RENDER.onrender.com/api/auth/gmail/callback
   ```
   *(Substitua pela URL real do backend no Render – você terá essa URL após o deploy no passo 3.)*

6. Clique em **Salvar**

> **Dica**: Se ainda não tiver a URL do Render, você pode voltar aqui depois do passo 3 e adicionar.

---

## 3. Render – Backend

### 3.1 Criar projeto via Blueprint

1. Acesse [render.com](https://render.com) e crie uma conta (ou faça login com GitHub)
2. No dashboard, clique em **New** → **Blueprint**
3. Conecte o repositório do projeto (se ainda não conectou)
4. O Render detectará o `render.yaml` na raiz do repositório
5. Clique em **Apply** – o Render criará o serviço web com a configuração do blueprint

> O `render.yaml` já define `rootDir: backend`, `buildCommand`, `startCommand` e `healthCheckPath`. As variáveis com `sync: false` precisarão ser preenchidas no passo 3.3.

### 3.2 Configuração alternativa (sem Blueprint)

Se preferir criar manualmente:

1. Clique em **New** → **Web Service**
2. Conecte o repositório e selecione o projeto
3. Configure:
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `sh scripts/start.sh`

### 3.3 Variáveis de ambiente

No Render, vá em **Environment** e adicione:

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | ✅ | URL do Supabase (passo 1.2) |
| `HF_TOKEN` ou `HUGGINGFACE_TOKEN` | ✅ | Token do [Hugging Face](https://huggingface.co/settings/tokens) (Inference) |
| `API_BASE_URL` | ✅ | URL do backend no Render (ex: `https://xxx.onrender.com`) |
| `FRONTEND_URL` | ✅ | URL do frontend na Vercel (ex: `https://xxx.vercel.app`) |
| `GOOGLE_CREDENTIALS_JSON` | ✅ | Conteúdo completo do `credentials.json` (JSON em uma linha) |
| `USER_NAME` | ⚪ | Seu nome para assinatura (quando Gmail não conectado) |
| `DISABLE_JOB_SCHEDULER` | ⚪ | `1` para desabilitar o job diário (opcional) |

O script `scripts/start.sh` cria o `credentials.json` a partir de `GOOGLE_CREDENTIALS_JSON` antes de iniciar o servidor.

### 3.4 Obter a URL do serviço

1. Após o primeiro deploy, o Render gera uma URL automática (ex: `https://email-classifier-api.onrender.com`)
2. Copie essa URL (sem barra no final)

### 3.5 Atualizar variáveis com a URL real

Com a URL do Render em mãos:

1. Atualize `API_BASE_URL` com essa URL (sem barra no final)
2. Volte ao [Google Cloud](#2-google-cloud---gmail-oauth) e adicione a URI de callback:
   ```
   https://SUA-URL-RENDER.onrender.com/api/auth/gmail/callback
   ```

### 3.6 Deploy

1. Faça push no GitHub – o Render faz deploy automático (se configurado)
2. Ou clique em **Manual Deploy** → **Deploy latest commit**
3. Aguarde o build e o deploy
4. Verifique os logs em **Logs**
5. Teste: `https://SUA-URL-RENDER.onrender.com/health` deve retornar `{"status":"healthy"}`

### 3.7 Plano Free e cold start

No plano **Free**, o serviço entra em sleep após ~15 min de inatividade. A primeira requisição após o sleep pode levar 30–60 segundos (cold start). Para evitar isso, use o plano **Starter** ($7/mês).

---

## 4. Vercel – Frontend

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

Em **Environment Variables**, adicione:

| Variável | Valor | Ambiente |
|----------|-------|----------|
| `NEXT_PUBLIC_API_URL` | `https://SUA-URL-RENDER.onrender.com` | Production, Preview, Development |

Use a URL do backend no Render (sem barra no final).

### 4.4 Deploy

1. Clique em **Deploy**
2. Aguarde o build
3. Copie a URL do projeto (ex: `https://test-controlar-emails.vercel.app`)

### 4.5 Atualizar backend

No Render, atualize a variável `FRONTEND_URL` com a URL do Vercel (para o redirect do OAuth funcionar corretamente).

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

- [ ] Supabase: projeto criado e `DATABASE_URL` obtida
- [ ] Google Cloud: URI de callback de produção adicionada
- [ ] Render: backend deployado, variáveis configuradas, URL gerada
- [ ] Vercel: frontend deployado, `NEXT_PUBLIC_API_URL` configurada
- [ ] `FRONTEND_URL` no Render apontando para a URL do Vercel
- [ ] `API_BASE_URL` no Render com a URL do Render
- [ ] Teste de health no backend
- [ ] Teste de classificação no frontend
- [ ] Teste de conexão Gmail

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
