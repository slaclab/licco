
// generic function for rendering an array or an regular entry in a default format
export function renderTableField(entry: any) {
    if (Array.isArray(entry)) {
        return entry.join(", ");
    }
    return entry;
}