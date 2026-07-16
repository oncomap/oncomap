// Mirrors build_site() in build/compile.py - the contract between the compiler
// and this app. Kept in lockstep with DATASET_COLUMNS + reusability().

export interface ReuseSignal {
  key: string;
  label: string;
  ok: boolean;
}

export interface Reusability {
  score: number;
  met: number;
  total: number;
  signals: ReuseSignal[];
}

export interface Dataset {
  id: string;
  title: string;
  cancer_type: string;
  cancer_type_name: string;
  cancer_type_ncit: string;
  tissue: string;
  tissue_label: string;
  modality: string;
  platform: string;
  sequencer: string;
  n_samples: number | string;
  n_patients: number | string;
  accession: string;
  access: string;
  curation_status: string;
  last_verified: string;
  deposition_year: number | string;
  source_paper: string;
  paper_doi: string;
  paper_year: number | string;
  lab: string;
  lab_name: string;
  pipeline_ref: string;
  method_name: string;
  reuse_notes: string;
  reusability?: Reusability;
}

export interface SiteData {
  generated_at?: string;
  version?: string;
  counts: { datasets: number; cancer_types: number };
  facets: {
    modality: string[];
    platform: string[];
    cancer_type: string[];
    access: string[];
    curation_status: string[];
  };
  datasets: Dataset[];
}
