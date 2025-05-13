import { sortString } from "./sort_utils";

/*
Calculates FCs that are valid choices for adding an FC to the project of modifying an existing FC.
*/
export function calculateValidFcs(allFcs: string[], usedFcs: string[], currentFc?: string): string[] {
    
    // remove all used FCs (duplicates are not allowed)
    var set = new Set(allFcs).difference(new Set(usedFcs));
    
    // current FC was removed as it is used, but keeping the value as-is is a valid option
    if (currentFc !== undefined) {
        set.add(currentFc);
    }

    // return an alphabetically sorted list
    return Array.from(set).sort((a, b) => sortString(a, b, false))
}