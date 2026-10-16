BEGIN;
INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types) VALUES
 ('nameplates','nameplates',false,10485760,ARRAY['image/jpeg','image/png','image/webp']),
 ('catalogue-evidence','catalogue-evidence',false,20971520,ARRAY['application/pdf']),
 ('imports','imports',false,10485760,ARRAY['text/csv','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']),
 ('exports','exports',false,20971520,ARRAY['application/pdf']);
CREATE FUNCTION public.partsiq_storage_allowed(object_name text, target_bucket text, write_access boolean) RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE actor uuid:=auth.uid(); allowed boolean:=false;
BEGIN
 IF actor IS NULL THEN RETURN false; END IF;
 IF target_bucket='nameplates' THEN
 SELECT EXISTS(SELECT 1 FROM enquiry_attachments a JOIN enquiries e ON e.id=a.enquiry_id
 WHERE a.storage_key=object_name AND e.owner_id=actor
 AND (e.session_id IS NULL OR app_private.demo_active(e.session_id,e.session_generation,actor))
 AND ((write_access AND a.status='pending') OR (NOT write_access AND a.status='validated'))) INTO allowed;
 END IF;
 RETURN allowed;
END; $$;
REVOKE ALL ON FUNCTION public.partsiq_storage_allowed(text,text,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.partsiq_storage_allowed(text,text,boolean) TO authenticated;
CREATE POLICY nameplate_insert ON storage.objects FOR INSERT TO authenticated
 WITH CHECK(bucket_id='nameplates' AND public.partsiq_storage_allowed(name,bucket_id,true));
CREATE POLICY nameplate_read ON storage.objects FOR SELECT TO authenticated
 USING(bucket_id='nameplates' AND public.partsiq_storage_allowed(name,bucket_id,false));
-- Other buckets have no end-user policy. Worker signs authorized downloads only after gateway scope validation.
COMMIT;
