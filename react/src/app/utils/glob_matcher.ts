export function createGlobMatchRegex(searchTerm: string, caseInsensitive: boolean = true): RegExp {
    if (searchTerm === "") {
        return new RegExp(".*"); // match all
    }
    const regex = new RegExp('^' + searchTerm.replace(/\*/g, '.*') + '$', caseInsensitive ? 'i' : undefined);
    return regex;
}