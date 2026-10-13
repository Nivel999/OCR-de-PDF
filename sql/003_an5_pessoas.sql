-- Migração idempotente: guarda todas as pessoas citadas no PDF, com o papel
-- atribuído pela LLM (proprietário, cônjuge, transmitente, credor etc.).
-- Rode depois de 001_processamento_pdf.sql; não há DROP nem recriação.
--
-- Formato de an5_pessoas (uma entrada por pessoa e por papel):
-- [{"nome": "MARIA DA SILVA", "cpf_cnpj": "123.456.789-00",
--   "papel": "proprietario", "descricao_papel": null,
--   "paginas": [1, 3], "evidencia": "Proprietária: MARIA DA SILVA"}]

BEGIN;

ALTER TABLE cadastro.midia
    ADD COLUMN IF NOT EXISTS an5_pessoas jsonb NULL;

COMMENT ON COLUMN cadastro.midia.an5_pessoas IS
    'OCR: todas as pessoas citadas no PDF, com papel (proprietario, proprietario_anterior, conjuge, adquirente, transmitente, credor, devedor, procurador, confrontante, oficial_cartorio, testemunha, outro), CPF/CNPJ, páginas e evidência';

COMMIT;

-- Exemplo: proprietários de cada mídia.
-- SELECT m.id, p->>'nome' AS nome, p->>'cpf_cnpj' AS cpf_cnpj
-- FROM cadastro.midia AS m, jsonb_array_elements(m.an5_pessoas) AS p
-- WHERE p->>'papel' = 'proprietario';
