import { invoke } from "@tauri-apps/api/core";
import type { Project, ProjectInput, ProjectPage, ProjectQuery, ProjectStats, ProjectUpdate } from "../../types/project";

export const projectApi = {
  create: (payload: ProjectInput) => invoke<Project>("create_project", { payload }),
  list: (query: ProjectQuery) => invoke<ProjectPage>("list_projects", {
    page: query.page,
    pageSize: query.pageSize,
    search: query.search || null,
    status: query.status ?? null,
    sortBy: query.sortBy,
    sortOrder: query.sortOrder,
  }),
  get: (projectId: number) => invoke<Project>("get_project", { projectId }),
  update: (projectId: number, payload: ProjectUpdate) => invoke<Project>("update_project", { projectId, payload }),
  delete: (projectId: number) => invoke<void>("delete_project", { projectId }),
  stats: () => invoke<ProjectStats>("project_stats"),
};
