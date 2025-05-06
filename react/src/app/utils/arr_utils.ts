
export function isArrayEqual<T>(a: T[], b: T[]) {
    if (a === undefined && b !== undefined || b === undefined && a !== undefined) {
        return false;
    }

    if (a.length !== b.length) {
        return false;
    }

    // every field should be equal
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) {
            return false;
        }
    }

    return true;
}