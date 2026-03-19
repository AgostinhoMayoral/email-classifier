# Guia de Deploy

## Resumo

- **Frontend**: Vercel (Next.js)
- **Backend**: Render (Python FastAPI)

## 1. Deploy do Backend (Render)

1. Acesse [render.com](https://render.com) e crie uma conta
2. **New** → **Web Service**
3. Conecte seu repositório GitHub
4. Configurações:
   - **Name**: `email-classifier-api`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables** (opcional):
   - `HF_TOKEN`: Seu token do Hugging Face (https://huggingface.co/settings/tokens)
6. Clique em **Create Web Service**
7. Aguarde o deploy e copie a URL (ex: `https://email-classifier-api.onrender.com`)

## 2. Deploy do Frontend (Vercel)

1. Acesse [vercel.com](https://vercel.com) e crie uma conta
2. **Add New** → **Project**
3. Importe o repositório do GitHub
4. Configurações:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Next.js (detectado automaticamente)
5. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL`: Cole a URL do backend no Render (ex: `https://email-classifier-api.onrender.com`)
6. Clique em **Deploy**
7. Aguarde e copie a URL do projeto

## 3. CORS

O backend já está configurado com `allow_origins=["*"]` para aceitar requisições de qualquer origem. Em produção, você pode restringir para o domínio do Vercel:

```python
# backend/app/main.py
allow_origins=["https://seu-projeto.vercel.app"]
```

## 4. Observações

- **Render Free Tier**: O backend pode "dormir" após 15 min de inatividade. A primeira requisição pode demorar ~30 segundos.
- **Hugging Face**: Sem o token, a aplicação usa classificação baseada em regras (funciona bem para a maioria dos casos).
- **Vercel**: O frontend é estático/SSR e não dorme.
