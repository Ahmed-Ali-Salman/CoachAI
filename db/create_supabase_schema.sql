-- Supabase schema for Multimodal Learning Coach
-- Run this in Supabase SQL editor (Project -> Database -> SQL)

-- Enable pgvector extension (Supabase-managed Postgres may already have it enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Lessons table
CREATE TABLE IF NOT EXISTS public.lessons (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id uuid NULL,
  title text,
  topic text,
  subject text,
  level text,
  content text,
  visibility text DEFAULT 'private',
  created_at timestamptz DEFAULT now()
);

-- Attachments table
CREATE TABLE IF NOT EXISTS public.attachments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id uuid NULL,
  bucket text,
  path text,
  public_url text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- User queries (text queries that users submit)
CREATE TABLE IF NOT EXISTS public.user_queries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NULL,
  text_query text,
  image_attachment_ids uuid[] DEFAULT ARRAY[]::uuid[],
  created_at timestamptz DEFAULT now()
);

-- Generated questions
CREATE TABLE IF NOT EXISTS public.generated_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lesson_id uuid NULL,
  query_id uuid NULL,
  author_model text,
  question_text text,
  created_at timestamptz DEFAULT now()
);

-- Answers (student answers + model answers)
CREATE TABLE IF NOT EXISTS public.answers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id uuid NULL,
  user_id uuid NULL,
  user_answer text,
  model_answer text,
  grade text,
  feedback text,
  created_at timestamptz DEFAULT now()
);

-- Embeddings table using pgvector
-- Adjust dimension to match PGVECTOR_DIMENSION (default 384)
CREATE TABLE IF NOT EXISTS public.embeddings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_table text NOT NULL,
  source_id uuid NOT NULL,
  embedding vector(384) NOT NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- Index for nearest-neighbor search
CREATE INDEX IF NOT EXISTS embeddings_embedding_idx ON public.embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Add relational columns and foreign keys to connect tables where appropriate.
-- Use idempotent ALTER statements (ADD COLUMN IF NOT EXISTS, DROP CONSTRAINT IF EXISTS).

-- Attachments: optionally link to lessons and user_queries
ALTER TABLE IF EXISTS public.attachments ADD COLUMN IF NOT EXISTS lesson_id uuid NULL;
ALTER TABLE IF EXISTS public.attachments ADD COLUMN IF NOT EXISTS query_id uuid NULL;
ALTER TABLE IF EXISTS public.attachments DROP CONSTRAINT IF EXISTS attachments_lesson_fk;
ALTER TABLE IF EXISTS public.attachments ADD CONSTRAINT attachments_lesson_fk FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE SET NULL;
ALTER TABLE IF EXISTS public.attachments DROP CONSTRAINT IF EXISTS attachments_query_fk;
ALTER TABLE IF EXISTS public.attachments ADD CONSTRAINT attachments_query_fk FOREIGN KEY (query_id) REFERENCES public.user_queries(id) ON DELETE SET NULL;

-- Generated questions: ensure FK to lessons and user_queries
ALTER TABLE IF EXISTS public.generated_questions DROP CONSTRAINT IF EXISTS generated_questions_lesson_fk;
ALTER TABLE IF EXISTS public.generated_questions ADD CONSTRAINT generated_questions_lesson_fk FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE SET NULL;
ALTER TABLE IF EXISTS public.generated_questions DROP CONSTRAINT IF EXISTS generated_questions_query_fk;
ALTER TABLE IF EXISTS public.generated_questions ADD CONSTRAINT generated_questions_query_fk FOREIGN KEY (query_id) REFERENCES public.user_queries(id) ON DELETE SET NULL;

-- Answers: link to generated_questions
ALTER TABLE IF EXISTS public.answers DROP CONSTRAINT IF EXISTS answers_question_fk;
ALTER TABLE IF EXISTS public.answers ADD CONSTRAINT answers_question_fk FOREIGN KEY (question_id) REFERENCES public.generated_questions(id) ON DELETE SET NULL;

-- Embeddings: provide optional direct foreign keys for common sources for easier joins
ALTER TABLE IF EXISTS public.embeddings ADD COLUMN IF NOT EXISTS lesson_id uuid NULL;
ALTER TABLE IF EXISTS public.embeddings ADD COLUMN IF NOT EXISTS query_id uuid NULL;
ALTER TABLE IF EXISTS public.embeddings ADD COLUMN IF NOT EXISTS generated_question_id uuid NULL;
ALTER TABLE IF EXISTS public.embeddings DROP CONSTRAINT IF EXISTS embeddings_lesson_fk;
ALTER TABLE IF EXISTS public.embeddings ADD CONSTRAINT embeddings_lesson_fk FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS public.embeddings DROP CONSTRAINT IF EXISTS embeddings_query_fk;
ALTER TABLE IF EXISTS public.embeddings ADD CONSTRAINT embeddings_query_fk FOREIGN KEY (query_id) REFERENCES public.user_queries(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS public.embeddings DROP CONSTRAINT IF EXISTS embeddings_generated_question_fk;
ALTER TABLE IF EXISTS public.embeddings ADD CONSTRAINT embeddings_generated_question_fk FOREIGN KEY (generated_question_id) REFERENCES public.generated_questions(id) ON DELETE CASCADE;

-- Note about RLS / Policies:
-- For development you can temporarily disable RLS or grant insert/select to the anon key.
-- For production, prefer server-side inserts (service role key) and RLS policies.

-- Example RLS disable (not recommended for production):
-- ALTER TABLE public.lessons ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY public_insert ON public.lessons FOR INSERT USING (true) WITH CHECK (true);

-- Row Level Security policies to ensure only the owner can view or modify their lessons
-- Enable RLS on lessons
ALTER TABLE IF EXISTS public.lessons ENABLE ROW LEVEL SECURITY;

-- Ensure idempotency: drop any existing policies then create them (Postgres
-- CREATE POLICY does not support IF NOT EXISTS)
DROP POLICY IF EXISTS lessons_owner_select ON public.lessons;
CREATE POLICY lessons_owner_select ON public.lessons
  FOR SELECT
  USING (owner_id::text = auth.uid());

DROP POLICY IF EXISTS lessons_owner_insert ON public.lessons;
CREATE POLICY lessons_owner_insert ON public.lessons
  FOR INSERT
  WITH CHECK (owner_id::text = auth.uid());

DROP POLICY IF EXISTS lessons_owner_update ON public.lessons;
CREATE POLICY lessons_owner_update ON public.lessons
  FOR UPDATE
  USING (owner_id::text = auth.uid())
  WITH CHECK (owner_id::text = auth.uid());

DROP POLICY IF EXISTS lessons_owner_delete ON public.lessons;
CREATE POLICY lessons_owner_delete ON public.lessons
  FOR DELETE
  USING (owner_id::text = auth.uid());

-- Note: The `service_role` key bypasses RLS. For front-end clients use anon key
-- and rely on policies, or call server-side endpoints that use the service role key.
