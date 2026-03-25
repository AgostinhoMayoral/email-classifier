-- Diagnóstico de integridade / "vestígios" — rode no DBeaver (prod ou dev PostgreSQL).
-- Esperado: contagens zero nas linhas de problema (exceto resumo final).

-- 1) Registros órfãos (não deveria existir se FKs estiverem ativas no banco)
SELECT 'classifications órfãs' AS check_name, COUNT(*) AS problem_rows
FROM email_classifications c
WHERE NOT EXISTS (SELECT 1 FROM email_records e WHERE e.id = c.email_record_id)
UNION ALL
SELECT 'logs órfãos', COUNT(*)
FROM email_logs l
WHERE NOT EXISTS (SELECT 1 FROM email_records e WHERE e.id = l.email_record_id);

-- 2) Mais de uma classificação por email (quebra o modelo 1:1)
SELECT 'duplicata classification por email_record_id' AS check_name, COUNT(*) AS problem_groups
FROM (
  SELECT email_record_id, COUNT(*) AS n
  FROM email_classifications
  GROUP BY email_record_id
  HAVING COUNT(*) > 1
) x;

-- 3) Duplicata de gmail_message_id (deveria falhar no INSERT se UNIQUE existir)
SELECT 'gmail_message_id duplicado' AS check_name, COUNT(*) AS problem_groups
FROM (
  SELECT gmail_message_id, COUNT(*) AS n
  FROM email_records
  WHERE gmail_message_id IS NOT NULL
  GROUP BY gmail_message_id
  HAVING COUNT(*) > 1
) x;

-- 4) Status fora dos valores usados pelo app
SELECT 'status inválido' AS check_name, status, COUNT(*) AS n
FROM email_records
WHERE status IS NULL
   OR status NOT IN ('pending', 'classified', 'sent', 'skipped', 'failed')
GROUP BY status;

-- 5) Categoria fora de Produtivo / Improdutivo (app normaliza na entrada nova; linhas antigas podem divergir)
SELECT 'category suspeita' AS check_name, category, COUNT(*) AS n
FROM email_classifications
WHERE category NOT IN ('Produtivo', 'Improdutivo')
GROUP BY category;

-- 6) Inconsistência status vs classificação (sinais de processo interrompido ou bug antigo)
SELECT 'classified sem linha em email_classifications' AS check_name, COUNT(*) AS n
FROM email_records r
WHERE r.status = 'classified'
  AND NOT EXISTS (SELECT 1 FROM email_classifications c WHERE c.email_record_id = r.id)
UNION ALL
SELECT 'tem classificação mas status ainda pending', COUNT(*)
FROM email_records r
WHERE r.status = 'pending'
  AND EXISTS (SELECT 1 FROM email_classifications c WHERE c.email_record_id = r.id);

-- 7) Versão Alembic registrada (vazio = ainda não rodou upgrade após introduzir Alembic)
SELECT 'alembic_version' AS info, version_num FROM alembic_version ORDER BY version_num;

-- 8) Resumo
SELECT 'email_records' AS tbl, COUNT(*) FROM email_records
UNION ALL SELECT 'email_classifications', COUNT(*) FROM email_classifications
UNION ALL SELECT 'email_logs', COUNT(*) FROM email_logs
UNION ALL SELECT 'job_configs', COUNT(*) FROM job_configs;
