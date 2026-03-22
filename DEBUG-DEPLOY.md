# Passo a passo para debugar o deploy

## FIX 404 VERCEL – Tente isso primeiro

Foi adicionado um `vercel.json` na raiz do projeto. Faça:

1. **Vercel** → projeto email-classifier → **Settings** → **Build and Deployment**
2. Em **Root Directory**: clique em **Edit** e **APAGUE** o valor (deixe vazio)
3. Clique em **Save**
4. **Deployments** → último deploy → **⋮** → **Redeploy** (com "Redeploy with existing Build Cache" **desligado**)
5. Aguarde o build e teste: https://email-classifier-ashy.vercel.app

Se ainda der 404, siga os passos abaixo para coletar informações.

---

## Coleta de informações (se o fix acima não funcionar)

Siga cada passo e **copie/cole aqui** o que aparecer. Assim consigo identificar o problema.

---

## PASSO 1: Vercel – Logs do último deploy

1. Acesse https://vercel.com/dashboard
2. Clique no projeto **email-classifier**
3. Clique na aba **Deployments**
4. Clique no **último deploy** (o primeiro da lista)
5. Na página do deploy, procure por **"Building"** ou **"Build Logs"** e clique
6. Role até o **FINAL** do log
7. **Copie e cole aqui** as últimas 30–50 linhas (onde aparece "Build Completed" ou qualquer erro em vermelho)

---

## PASSO 2: Vercel – Configuração atual

1. No projeto, vá em **Settings** (menu lateral)
2. Clique em **Build and Deployment**
3. Tire um **print** ou anote e me envie:
   - Root Directory: `_______`
   - Framework Preset: `_______`
   - Build Command: `_______`
   - Output Directory: `_______`
4. Vá em **Environment Variables**
5. Liste as variáveis que aparecem (só o **nome**, não o valor por segurança):
   - Ex: NEXT_PUBLIC_API_URL, etc.

---

## PASSO 3: Render – Logs do backend

1. Acesse https://dashboard.render.com
2. Clique no serviço do backend (email-classifier ou similar)
3. Clique em **Logs** (menu lateral)
4. Role até as últimas linhas
5. **Copie e cole aqui** as últimas 20–30 linhas (qualquer erro em vermelho ou mensagem de startup)

---

## PASSO 4: Render – Status do serviço

1. No Render, na página do serviço
2. Me diga: o status está **"Live"** (verde) ou **"Suspended"** / outro?
3. Qual é a **URL** que aparece no topo? (ex: https://email-classifier-wkq6.onrender.com)

---

## PASSO 5: Teste manual (opcional)

1. Abra uma nova aba no navegador
2. Cole esta URL: `https://email-classifier-wkq6.onrender.com/health`
3. Aperte Enter
4. Me diga o que aparece:
   - Carrega e mostra `{"status":"healthy"}`?
   - Fica carregando e não termina?
   - Mostra erro (qual?)
   - Outra coisa?

---

## Resumo – o que preciso que você envie

1. Últimas linhas do **Build Log** da Vercel (Passo 1)
2. Configuração da Vercel (Passo 2)
3. Últimas linhas dos **Logs** do Render (Passo 3)
4. Status e URL do Render (Passo 4)
5. Resultado do teste em `/health` (Passo 5)

Com isso consigo te orientar passo a passo para corrigir.
