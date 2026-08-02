import { create } from "zustand";

export interface Artifact {
  id: string;
  title: string;
  type: string;
}

interface ArtifactStore {
  artifacts: Artifact[];

  setArtifacts: (artifacts: Artifact[]) => void;
}

export const useArtifactStore = create<ArtifactStore>((set) => ({
  artifacts: [],

  setArtifacts: (artifacts) =>
    set({
      artifacts,
    }),
}));