# Email Classifier - Classificação Inteligente de Emails

Solução digital para automatizar a leitura e classificação de emails corporativos, utilizando inteligência artificial para categorizar mensagens e sugerir respostas automáticas.

## Funcionalidades

- **Classificação automática**: Emails categorizados em **Produtivo** (requer ação) ou **Improdutivo** (não requer ação)
- **Sugestão de respostas**: Respostas automáticas adequadas à categoria identificada
- **Múltiplos formatos**: Upload de arquivos .txt ou .pdf, ou inserção direta de texto
- **Pré-processamento NLP**: Remoção de stop words, lemmatização e normalização de texto
- **IA flexível**: Hugging Face Inference API com fallback para classificação baseada em regras

## Arquitetura

```
├── frontend/          # Next.js 16 + TypeScript + Tailwind
├── backend/           # Python FastAPI + NLP
├── sample-emails/     # Emails de exemplo para testes
└── README.md
```

## Pré-requisitos

- Node.js 18+
- Python 3.10+
- (Opcional) Token Hugging Face para classificação com IA

## Executando localmente

### 1. Backend (Python)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

O backend estará em `http://localhost:8000`

**Variáveis de ambiente** (opcional):
- `HF_TOKEN` ou `HUGGINGFACE_TOKEN`: Token da API Hugging Face para classificação com IA. Sem o token, a aplicação usa classificação baseada em regras.

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

O frontend estará em `http://localhost:3000`

**Variáveis de ambiente**:
- `NEXT_PUBLIC_API_URL`: URL do backend (padrão: `http://localhost:8000`)

### 3. Testar

1. Acesse http://localhost:3000
2. Faça upload de um arquivo da pasta `sample-emails/` ou cole um texto
3. Clique em "Classificar e sugerir resposta"
4. Veja a categoria e a resposta sugerida

## Deploy na nuvem

### Backend (Render)

1. Crie uma conta em [Render.com](https://render.com)
2. New → Web Service
3. Conecte o repositório e configure:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment**: Adicione `HF_TOKEN` (opcional)

### Frontend (Vercel)

1. Crie uma conta em [Vercel.com](https://vercel.com)
2. Importe o repositório
3. Configure:
   - **Root Directory**: `frontend`
   - **Environment Variable**: `NEXT_PUBLIC_API_URL` = URL do backend no Render

### Alternativas

- **Backend**: Railway, Fly.io, Google Cloud Run, AWS Lambda
- **Frontend**: Netlify, Cloudflare Pages

## Tecnologias

| Camada | Tecnologias |
|--------|-------------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, Uvicorn |
| NLP | NLTK (tokenização, stop words, lemmatização) |
| IA | Hugging Face Inference API (BART zero-shot, Flan-T5) |
| Arquivos | PyPDF2 (extração de PDF) |

## Estrutura do Backend

```
backend/
├── app/
│   ├── main.py              # API FastAPI
│   └── services/
│       ├── processor.py     # Classificação e geração de resposta
│       ├── nlp_preprocessor.py
│       └── text_extractor.py
├── requirements.txt
└── .env.example
```

## API

### POST /api/classify

Classifica um email e retorna sugestão de resposta.

**Entrada** (multipart/form-data):
- `file`: Arquivo .txt ou .pdf (opcional)
- `text`: Texto do email (opcional)

**Resposta**:
```json
{
  "category": "Produtivo",
  "confidence": 0.92,
  "suggested_response": "Prezado(a),\n\nAgradecemos o contato...",
  "processed_text": "solicit atualiz status requisit..."
}
```

## Licença

MIT
