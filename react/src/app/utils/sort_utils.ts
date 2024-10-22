
// helper for changing sort order of clicked table columns
export class SortState<T> {
    constructor(public column: T, public sortDesc: boolean = true) { }

    public changed(clickedColumn: T): SortState<T> {
        if (clickedColumn == this.column) {
            // same field was clicked, change the sort order
            let newSortOrder = !this.sortDesc;
            return new SortState(clickedColumn, newSortOrder);
        }

        // different field was clicked, use the default sort order
        return new SortState(clickedColumn);
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
    // regardless of asc or desc sorting order
    if (a == "" && b == "") {
        return 0;
    }
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
    // regardless of asc or desc sorting order
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

function toUnixMs(a: Date): number {
    return a.getTime();
}

export function sortDate(a?: Date, b?: Date, desc: boolean = true) {
    let timeA = a ? toUnixMs(a) : 0;
    let timeB = b ? toUnixMs(b) : 0;
    let diff = timeB - timeA;
    return desc ? diff : -diff;
}