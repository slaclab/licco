export function createGlobMatchRegex(searchTerm: string): RegExp {
    if (searchTerm === "") {
        return new RegExp(".*"); // match all
    }
    const regex = new RegExp('^' + searchTerm.replace(/\*/g, '.*') + '$');
    return regex;
}