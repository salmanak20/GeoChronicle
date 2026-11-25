export type ProjectStatus = "draft" | "in_progress" | "completed" | "archived";
export type ProjectSort = "created_at" | "updated_at";

export interface Project {
  id: number;
  name: string;
  description: string | null;
  topic: string | null;
  status: ProjectStatus;
  target_duration_seconds: number | null;
  aspect_ratio: string;
  language: string;
  visual_style: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectInput {
  name: string;
  description: string | null;
  topic: string | null;
  target_duration_seconds: number | null;
  aspect_ratio: string;
  language: string;
  visual_style: string;
}

export type ProjectUpdate = Partial<ProjectInput> & { status?: ProjectStatus };

export interface ProjectPage {
  items: Project[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ProjectStats {
  total: number;
  draft: number;
  in_progress: number;
  completed: number;
  recently_updated: Project[];
}

export interface ProjectQuery {
  page: number;
  pageSize: number;
  search?: string;
  status?: ProjectStatus;
  sortBy: ProjectSort;
  sortOrder: "asc" | "desc";
}

export const projectStatusLabels: Record<ProjectStatus, string> = {
  draft: "Draft",
  in_progress: "In progress",
  completed: "Completed",
  archived: "Archived",
};
