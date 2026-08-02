import { useArtifactStore } from "../stores/artifactStore";

export function useArtifacts() {
  return useArtifactStore();
}