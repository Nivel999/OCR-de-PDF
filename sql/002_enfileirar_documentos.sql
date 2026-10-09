-- Enfileira para o pipeline as mídias de:
--   12 = Memorial Descritivo do INCRA
--   13 = Matrícula
-- (cadastro.midia.tipo_documento, domínio dominio.tipo_documento)
-- Páginas com texto nativo são lidas direto; só as escaneadas passam por OCR.
-- Executar depois de 001_processamento_pdf.sql. Pode ser repetido: só marca
-- mídias que ainda não passaram pelo pipeline (an5_status IS NULL).

-- 1. Conferir antes: quantas mídias de cada tipo entrariam na fila.
SELECT tipo_documento, count(*) AS midias
FROM cadastro.midia
WHERE tipo_documento IN (12, 13)
  AND link IS NOT NULL AND link <> ''
  AND an5_status IS NULL
GROUP BY tipo_documento;

-- 2. Enfileirar.
UPDATE cadastro.midia
SET an5_status = 'pendente', an5_tentativas = 0
WHERE tipo_documento IN (12, 13)
  AND link IS NOT NULL AND link <> ''
  AND an5_status IS NULL;
