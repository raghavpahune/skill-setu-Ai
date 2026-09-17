ALTER TABLE gov_opportunities ADD COLUMN IF NOT EXISTS verification_status TEXT;
ALTER TABLE gov_opportunities ADD COLUMN IF NOT EXISTS source_type TEXT;

ALTER TABLE schemes ADD COLUMN IF NOT EXISTS target_skills TEXT[] DEFAULT '{}';
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS data_provenance TEXT;
