# Guia de Deploy Completo

## Resumo da arquitetura

| Componente | Serviço   | URL (exemplo)                    |
|------------|-----------|-----------------------------------|
| **Banco de dados** | Supabase  | `postgresql://...@db.xxx.supabase.co:5432/postgres` |
| **Backend**        | Railway   | `https://seu-projeto.up.railway.app` |
| **Frontend**       | Vercel    | `https://seu-projeto.vercel.app`     |

---

## Ordem de execução

Siga os passos **nesta ordem**, pois cada etapa depende da anterior.

1. [Supabase](#1-supabase---banco-de-dados) – criar projeto e obter `DATABASE_URL`
2. [Google Cloud](#2-google-cloud---gmail-oauth) – configurar URIs de produção
3. [Railway](#3-railway---backend) – deploy do backend
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

Guarde essa URL – você usará como `DATABASE_URL` no Railway.

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
   https://SEU-BACKEND-RAILWAY.up.railway.app/api/auth/gmail/callback
   ```
   *(Substitua pela URL real do backend no Railway – você terá essa URL após o deploy no passo 3.)*

6. Clique em **Salvar**

> **Dica**: Se ainda não tiver a URL do Railway, você pode voltar aqui depois do passo 3 e adicionar.

---

## 3. Railway – Backend

### 3.1 Criar projeto

1. Acesse [railway.app](https://railway.app) e crie uma conta (ou faça login com GitHub)
2. Clique em **New Project**
3. Selecione **Deploy from GitHub repo**
4. Conecte o repositório e escolha o repositório do projeto
5. Railway detectará o projeto – **não** clique em Deploy ainda

### 3.2 Configurar o serviço

1. Clique no serviço criado para abrir as configurações
2. Vá em **Settings**
3. Configure:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: deixe em branco ou use `sh scripts/start.sh` (o `railway.toml` já define isso)
   - **Watch Paths**: `backend/**` (opcional, para rebuild em mudanças no backend)

> O arquivo `backend/railway.toml` já define o comando de start. Se o Railway não detectar, defina manualmente: `sh scripts/start.sh`

### 3.3 Variáveis de ambiente

Vá em **Variables** e adicione:

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | ✅ | URL do Supabase (passo 1.2) |
| `HF_TOKEN` ou `HUGGINGFACE_TOKEN` | ✅ | Token do [Hugging Face](https://huggingface.co/settings/tokens) (Inference) |
| `API_BASE_URL` | ✅ | URL do backend no Railway (ex: `https://xxx.up.railway.app`) |
| `FRONTEND_URL` | ✅ | URL do frontend na Vercel (ex: `https://xxx.vercel.app`) |
| `USER_NAME` | ⚪ | Seu nome para assinatura (quando Gmail não conectado) |
| `DISABLE_JOB_SCHEDULER` | ⚪ | `1` para desabilitar o job diário (opcional) |

### 3.4 Credenciais do Google (Gmail OAuth)

O `credentials.json` não pode ser commitado. Use uma variável de ambiente:

1. Abra o arquivo `credentials.json` do seu projeto (pasta `backend/`)
2. Copie o conteúdo completo (JSON em uma linha ou formatado)
3. No Railway, em **Variables**, adicione:
   - **Nome**: `GOOGLE_CREDENTIALS_JSON`
   - **Valor**: cole o JSON completo (tudo entre `{` e `}`)

4. Altere o **Start Command** para:

   ```bash
   sh scripts/start.sh
   ```

   O script `scripts/start.sh` cria o `credentials.json` a partir da variável `GOOGLE_CREDENTIALS_JSON` antes de iniciar o servidor.

### 3.5 Gerar domínio público

1. Em **Settings**, vá em **Networking**
2. Clique em **Generate Domain**
3. Copie a URL gerada (ex: `https://test-controlar-emails-production.up.railway.app`)

### 3.6 Atualizar variáveis com a URL real

Com a URL do Railway em mãos:

1. Atualize `API_BASE_URL` com essa URL (sem barra no final)
2. Volte ao [Google Cloud](#2-google-cloud---gmail-oauth) e adicione a URI de callback:
   ```
   https://SUA-URL-RAILWAY.up.railway.app/api/auth/gmail/callback
   ```

### 3.7 Deploy

1. Clique em **Deploy** (ou faça push no GitHub para deploy automático)
2. Aguarde o build e o deploy
3. Verifique os logs em **Deployments** → último deploy → **View Logs**
4. Teste: `https://SUA-URL-RAILWAY.up.railway.app/health` deve retornar `{"status":"healthy"}`

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
| `NEXT_PUBLIC_API_URL` | `https://SUA-URL-RAILWAY.up.railway.app` | Production, Preview, Development |

Use a URL do backend no Railway (sem barra no final).

### 4.4 Deploy

1. Clique em **Deploy**
2. Aguarde o build
3. Copie a URL do projeto (ex: `https://test-controlar-emails.vercel.app`)

### 4.5 Atualizar backend

No Railway, atualize a variável `FRONTEND_URL` com a URL do Vercel (para o redirect do OAuth funcionar corretamente).

---

## 5. Testar o deploy

### 5.1 Health check

- Backend: `https://SUA-URL-RAILWAY.up.railway.app/health`
- Deve retornar: `{"status":"healthy"}`

### 5.2 Frontend

1. Acesse a URL do Vercel
2. Teste a classificação de email (texto ou arquivo)
3. Conecte o Gmail (botão **Conectar Gmail**)
4. Autorize no Google e verifique se os emails aparecem

### 5.3 Gmail em produção

- **Tokens**: O `gmail_tokens.json` é efêmero no Railway. A cada novo deploy, será necessário **reconectar o Gmail** uma vez.
- Para evitar isso no futuro, os tokens podem ser persistidos no banco (Supabase) – isso exigiria alteração no código.

---

## 6. Checklist final

- [ ] Supabase: projeto criado e `DATABASE_URL` obtida
- [ ] Google Cloud: URI de callback de produção adicionada
- [ ] Railway: backend deployado, variáveis configuradas, domínio gerado
- [ ] Vercel: frontend deployado, `NEXT_PUBLIC_API_URL` configurada
- [ ] `FRONTEND_URL` no Railway apontando para a URL do Vercel
- [ ] `API_BASE_URL` no Railway com a URL do Railway
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
| Railway   | Hobby   | $5 crédito/mês (~$2–5) |
| Vercel    | Hobby   | Grátis                 |
| Hugging Face | Free | Grátis (com limites)   |

---

## 9. Troubleshooting

### Backend não inicia

- Verifique os logs no Railway
- Confirme que `DATABASE_URL` está correta (porta 6543 para Supabase pooler)
- Confirme que `GOOGLE_CREDENTIALS_JSON` está como JSON válido

### Erro de CORS

- Verifique se `NEXT_PUBLIC_API_URL` no frontend está correta
- Confirme que `FRONTEND_URL` no backend está correta

### Gmail "redirect_uri_mismatch"

- Adicione exatamente a URL de callback no Google Cloud:
  `https://SUA-URL-RAILWAY.up.railway.app/api/auth/gmail/callback`
- Sem barra no final, com `https://`

### Tabelas não existem

O backend cria as tabelas automaticamente no primeiro request (`init_db`). Se houver erro, verifique a conexão com o Supabase e as permissões do usuário.
