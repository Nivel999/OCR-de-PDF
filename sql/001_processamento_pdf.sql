-- Migração idempotente para o modo --banco do OCR-de-PDF.
-- Todos os resultados ficam em cadastro.midia, em colunas com prefixo an5_.
-- Pode ser executada em um banco que já possui cadastro.midia com dados:
-- não há DROP nem recriação; apenas cria o que estiver faltando.
--
-- Ciclo de an5_status: NULL (fora do pipeline) -> 'pendente' (enfileirado
-- manualmente) -> 'processando' -> 'concluido' | 'reutilizado' | 'falha'.

BEGIN;

ALTER TABLE cadastro.midia
    ADD COLUMN IF NOT EXISTS an5_matricula          text          NULL,
    ADD COLUMN IF NOT EXISTS an5_nome_imovel        text          NULL,
    ADD COLUMN IF NOT EXISTS an5_area_total_imovel  text          NULL,
    ADD COLUMN IF NOT EXISTS an5_confianca_media    numeric(5, 2) NULL,
    ADD COLUMN IF NOT EXISTS an5_descricao          text          NULL,
    ADD COLUMN IF NOT EXISTS an5_referencia         text          NULL,
    ADD COLUMN IF NOT EXISTS an5_status             varchar(20)   NULL
        CONSTRAINT midia_an5_status_ck CHECK (an5_status IN
            ('pendente', 'processando', 'concluido', 'reutilizado', 'falha')),
    ADD COLUMN IF NOT EXISTS an5_tentativas         int2          NOT NULL DEFAULT 0
        CONSTRAINT midia_an5_tentativas_ck CHECK (an5_tentativas >= 0),
    ADD COLUMN IF NOT EXISTS an5_data_transformacao timestamp     NULL,
    ADD COLUMN IF NOT EXISTS an5_pdf_sha256         bpchar(64)    NULL;

-- A área é gravada exatamente como escrita no documento, ex.:
-- 'Área (Sistema Geodésico Local): 35,2723 ha'. Se a coluna já existia como
-- número, converte para texto (sem perda: o número vira sua forma textual).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'cadastro' AND table_name = 'midia'
          AND column_name = 'an5_area_total_imovel' AND data_type <> 'text'
    ) THEN
        ALTER TABLE cadastro.midia
            ALTER COLUMN an5_area_total_imovel TYPE text USING an5_area_total_imovel::text;
    END IF;
END $$;

COMMENT ON COLUMN cadastro.midia.an5_matricula IS 'OCR: matrícula do imóvel extraída do PDF';
COMMENT ON COLUMN cadastro.midia.an5_nome_imovel IS 'OCR: nome do imóvel extraído do PDF';
COMMENT ON COLUMN cadastro.midia.an5_area_total_imovel IS 'OCR: área total exatamente como escrita no documento (rótulo, sistema e unidade)';
COMMENT ON COLUMN cadastro.midia.an5_confianca_media IS 'OCR: confiança média do Tesseract (0-100)';
COMMENT ON COLUMN cadastro.midia.an5_descricao IS 'OCR: descrição do resultado da confiança (ou do erro, se falha)';
COMMENT ON COLUMN cadastro.midia.an5_referencia IS 'OCR: resumo dos dados trazidos pelo OCR/INCRA';
COMMENT ON COLUMN cadastro.midia.an5_status IS 'OCR: pendente, processando, concluido, reutilizado ou falha';
COMMENT ON COLUMN cadastro.midia.an5_tentativas IS 'OCR: quantas vezes o processamento foi iniciado (falha definitiva na 2ª)';
COMMENT ON COLUMN cadastro.midia.an5_data_transformacao IS 'OCR: data/hora do último processamento';
COMMENT ON COLUMN cadastro.midia.an5_pdf_sha256 IS 'OCR: SHA-256 do PDF processado (deduplicação)';

-- Índices parciais: só cobrem linhas do pipeline, então ficam pequenos.
CREATE INDEX IF NOT EXISTS idx_midia_an5_status
    ON cadastro.midia (an5_status, id) WHERE an5_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_midia_an5_pdf_sha256
    ON cadastro.midia (an5_pdf_sha256) WHERE an5_pdf_sha256 IS NOT NULL;

COMMIT;

-- Para enfileirar mídias, use 002_enfileirar_documentos.sql.
