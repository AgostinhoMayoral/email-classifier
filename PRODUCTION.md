# Configuração de Produção - Email Classifier

## URLs de Produção

| Serviço  | URL                                      |
|----------|------------------------------------------|
| Frontend | https://email-classifier-ashy.vercel.app |
| Backend  | https://email-classifier-wkq6.onrender.com |
| Banco    | Supabase (variável `DATABASE_URL`)       |

---

## Variáveis por plataforma

### Vercel (Frontend)

| Variável              | Valor                                                |
|-----------------------|------------------------------------------------------|
| `NEXT_PUBLIC_API_URL` | `https://email-classifier-wkq6.onrender.com`         |

**Onde configurar:** Project Settings → Environment Variables  
**Ambiente:** Production, Preview, Development

---

### Render (Backend)

| Variável                 | Valor                                                |
|--------------------------|------------------------------------------------------|
| `API_BASE_URL`           | `https://email-classifier-wkq6.onrender.com`         |
| `FRONTEND_URL`           | `https://email-classifier-ashy.vercel.app`           |
| `DATABASE_URL`           | URL do Supabase (pooler, porta 6543)                 |
| `HF_TOKEN`               | Token do Hugging Face                                |
| `GOOGLE_CREDENTIALS_JSON`| Conteúdo do `credentials.json`                       |

---

### Google Cloud (OAuth)

**URIs de redirecionamento autorizados:**

```
https://email-classifier-wkq6.onrender.com/api/auth/gmail/callback
http://localhost:8000/api/auth/gmail/callback
```

**Origens JavaScript autorizadas:**

```
https://email-classifier-ashy.vercel.app
http://localhost:3000
http://localhost:8000
```

---

## Checklist de verificação

- [ ] Vercel: `NEXT_PUBLIC_API_URL` = `https://email-classifier-wkq6.onrender.com`
- [ ] Vercel: Root Directory = `frontend`
- [ ] Render: `API_BASE_URL` = `https://email-classifier-wkq6.onrender.com`
- [ ] Render: `FRONTEND_URL` = `https://email-classifier-ashy.vercel.app`
- [ ] Google Cloud: callback e origens configuradas
- [ ] Supabase: `DATABASE_URL` no Render
