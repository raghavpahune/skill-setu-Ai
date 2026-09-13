DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'sync_logs'
    ) THEN
        ALTER TABLE public.sync_logs DROP CONSTRAINT IF EXISTS sync_logs_status_check;
        ALTER TABLE public.sync_logs ADD CONSTRAINT sync_logs_status_check CHECK (status IN ('running', 'success', 'failed', 'partial', 'no_data', 'NO_DATA'));
    END IF;
END $$;
