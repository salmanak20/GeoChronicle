import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectForm } from "./ProjectForm";
import { ProjectWorkspace } from "./ProjectWorkspace";
import { projectApi } from "./projectApi";
import type { Project } from "../../types/project";

vi.mock("./projectApi", () => ({
  projectApi: {
    create: vi.fn(), list: vi.fn(), get: vi.fn(), update: vi.fn(), delete: vi.fn(), stats: vi.fn(),
  },
}));

const record = {
  id: 8,
  name: "The Silk Road",
  description: "A story about trade and exchange.",
  topic: "Central Asia",
  status: "draft" as const,
  target_duration_seconds: 600,
  aspect_ratio: "16:9",
  language: "en",
  visual_style: "hybrid",
  created_at: "2026-11-25T10:00:00Z",
  updated_at: "2026-11-25T11:00:00Z",
};

const page = (items: Project[] = [record]) => ({ items, total: items.length, page: 1, page_size: 8, pages: items.length ? 1 : 0 });

beforeEach(() => vi.clearAllMocks());

describe("ProjectForm", () => {
  it("validates a required project name before submitting", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ProjectForm onCancel={vi.fn()} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a project name");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a valid create form with defaults", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ProjectForm onCancel={vi.fn()} onSubmit={onSubmit} />);
    await user.type(screen.getByLabelText(/Project name/), "A New Story");
    await user.type(screen.getByLabelText("Topic"), "World history");
    await user.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: "A New Story", topic: "World history", aspect_ratio: "16:9", visual_style: "hybrid" })));
  });

  it("prepopulates project fields and status in edit mode", () => {
    render(<ProjectForm initial={{ ...record, status: "completed" }} onCancel={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText(/Project name/)).toHaveValue("The Silk Road");
    expect(screen.getByLabelText("Topic")).toHaveValue("Central Asia");
    expect(screen.getByLabelText("Project status")).toHaveValue("completed");
  });
});

describe("ProjectWorkspace", () => {
  it("renders loaded projects and filters them through the API", async () => {
    const user = userEvent.setup();
    vi.mocked(projectApi.list).mockImplementation(async query => query.search ? page([]) : page());
    render(<ProjectWorkspace onDataChanged={vi.fn()} />);
    expect(await screen.findByText("The Silk Road")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Search projects or topics" }), "Atlantis");
    expect(await screen.findByText("No matching projects")).toBeInTheDocument();
    expect(projectApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ search: "Atlantis" }));
  });

  it("shows a useful empty state", async () => {
    vi.mocked(projectApi.list).mockResolvedValue(page([]));
    render(<ProjectWorkspace onDataChanged={vi.fn()} />);
    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
  });

  it("requires confirmation and preserves the project when delete fails", async () => {
    const user = userEvent.setup();
    vi.mocked(projectApi.get).mockResolvedValue(record);
    vi.mocked(projectApi.delete).mockRejectedValue("Delete was rejected");
    render(<ProjectWorkspace initialProjectId={record.id} onDataChanged={vi.fn()} />);
    await screen.findByRole("heading", { name: "The Silk Road." });
    await user.click(screen.getByRole("button", { name: /^Delete$/ }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/The Silk Road/)).toBeInTheDocument();
    expect(projectApi.delete).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Delete project" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Delete was rejected");
    expect(screen.getByRole("heading", { name: "The Silk Road." })).toBeInTheDocument();
  });
});
