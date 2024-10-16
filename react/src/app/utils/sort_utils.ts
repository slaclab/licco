
// helper for changing sort order of clicked table columns
export class SortState<T> {
    constructor(public sortField: T, public sortDesc: boolean = true) { }

    public fieldClicked(clickedField: T): SortState<T> {
        if (clickedField == this.sortField) {
            // same field was clicked, change the sort order
            let newSortOrder = !this.sortDesc;
            return new SortState(clickedField, newSortOrder);
        }

        // different field was clicked, use the default sort order
        return new SortState(clickedField);
    }
}

export function sortString(a?: string, b?: string, desc: boolean = true) {
    a = a ?? '';
    b = b ?? '';
    if (a != "" && b != "") {
        let diff = a.localeCompare(b);
        return desc ? -diff : diff;
    }

    // ensures that empty fields are always at the bottom
    if (a == "") {
        return 1;
    }
    if (b == "") {
        return -1;
    }
    return 0;
}


export function sortNumber(a?: number, b?: number, desc: boolean = true) {
    if (a !== undefined && b !== undefined) {
        let diff = b - a;
        return desc ? diff : -diff;
    }

    // ensures that empty fields are always at the bottom 
    // either a or b is undefined
    // number that don't exist should be demoted to the bottom (when desc order is used)
    if (a === undefined && b === undefined) {
        return 0;
    }

    if (a === undefined) {
        return 1;
    }

    if (b === undefined) {
        return -1;
    }

    return 0;
}