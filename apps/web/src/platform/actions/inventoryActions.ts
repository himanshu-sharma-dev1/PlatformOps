// @ts-nocheck
import { createInventoryLoadActions } from "./inventoryLoadActions";
import { createInventoryEditorActions } from "./inventoryEditorActions";
import { createInventoryDeployActions } from "./inventoryDeployActions";
export function createInventoryActions(s: any) {
  return {
    ...createInventoryLoadActions(s),
    ...createInventoryEditorActions(s),
    ...createInventoryDeployActions(s),
  };
}
