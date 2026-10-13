/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ADMIN_PASSWORD: string;
  readonly VITE_OFFICER_PASSWORD: string;
  readonly VITE_COORDINATOR_PASSWORD: string;
  readonly VITE_RECRUITER_PASSWORD: string;
  readonly VITE_STUDENT_PASSWORD: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
