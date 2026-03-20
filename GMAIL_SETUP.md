# Configuração do Gmail (OAuth 2.0)

Para usar a leitura automática de emails do Gmail, é necessário configurar um projeto no Google Cloud Console e obter as credenciais OAuth.

## Passo a passo

### 1. Criar projeto no Google Cloud

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto ou selecione um existente
3. No menu lateral, vá em **APIs e Serviços** → **Biblioteca**
4. Pesquise por **Gmail API** e clique em **Ativar**

### 2. Configurar tela de consentimento OAuth

1. Vá em **APIs e Serviços** → **Tela de permissão OAuth** (ou "Tela de consentimento OAuth")
2. Escolha **Externo** (para testes com qualquer conta Google)
3. Preencha:
   - **Nome do app**: Email Classifier (ou outro nome)
   - **E-mail de suporte**: seu email
   - **Domínios autorizados**: deixe em branco para localhost
4. Em **Escopos**, adicione:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/gmail.compose`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
5. Adicione usuários de teste (seu email) se o app estiver em modo de teste
6. Salve e continue

### 3. Criar credenciais OAuth

1. Vá em **APIs e Serviços** → **Credenciais**
2. Clique em **+ Criar credenciais** → **ID do cliente OAuth**
3. Tipo de aplicativo: **Aplicativo da Web**
4. Nome: `Email Classifier` (ou outro)
5. Em **URIs de redirecionamento autorizados**, adicione:
   - **Local**: `http://localhost:8000/api/auth/gmail/callback`
   - **Produção**: `https://SEU-BACKEND.com/api/auth/gmail/callback`
6. Clique em **Criar**
7. Baixe o JSON (ícone de download) e salve como `credentials.json`
8. Coloque o arquivo na pasta `backend/` do projeto

### 4. Estrutura do credentials.json

O arquivo deve ter esta estrutura (o Google gera automaticamente):

```json
{
  "web": {
    "client_id": "SEU_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "seu-projeto",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "SEU_CLIENT_SECRET",
    "redirect_uris": [
      "http://localhost:8000/api/auth/gmail/callback"
    ]
  }
}
```

### 5. Variáveis de ambiente (opcional)

No `.env` do backend:

```env
# URL base da API (para OAuth redirect)
API_BASE_URL=http://localhost:8000

# URL do frontend (para redirect após login)
FRONTEND_URL=http://localhost:3000

# Caminho customizado para credentials (opcional)
# GOOGLE_CREDENTIALS_PATH=./credentials.json
```

Para produção:

```env
API_BASE_URL=https://api.seudominio.com
FRONTEND_URL=https://seudominio.com
```

### 6. Testar

1. Inicie o backend: `cd backend && uvicorn app.main:app --reload --port 8000`
2. Inicie o frontend: `cd frontend && npm run dev`
3. Acesse http://localhost:3000
4. Clique em **Conectar Gmail**
5. Faça login com sua conta Google e autorize o acesso
6. Os emails da caixa de entrada aparecerão automaticamente

## Permissão de envio (OBRIGATÓRIO para enviar emails)

Para **enviar** respostas automáticas, os escopos `gmail.send` e `gmail.compose` precisam estar na **Tela de consentimento OAuth**:

1. Vá em **APIs e Serviços** → **Tela de consentimento OAuth**
2. Clique em **EDITAR APP**
3. Avance até **Escopos** e clique em **ADICIONAR OU REMOVER ESCOPOS**
4. Pesquise e marque:
   - `.../auth/gmail.send` — "Enviar email em seu nome"
   - `.../auth/gmail.compose` — "Criar rascunhos e enviar emails"
5. **Salve** e continue

Depois, **apague o arquivo** `backend/gmail_tokens.json` (se existir) e conecte o Gmail novamente. Sem esses escopos na tela de consentimento, o Google não concede permissão de envio.

## Segurança

- **Nunca** faça commit de `credentials.json` ou `gmail_tokens.json`
- Esses arquivos já estão no `.gitignore`
- Em produção, use variáveis de ambiente para secrets
- O `gmail_tokens.json` é gerado automaticamente após o primeiro login

## Modo de teste vs produção

Enquanto o app estiver em **modo de teste** no Google Cloud, apenas os usuários adicionados em "Usuários de teste" poderão fazer login. Para liberar para qualquer conta Google, é necessário enviar o app para **verificação** no Google (processo mais demorado).
