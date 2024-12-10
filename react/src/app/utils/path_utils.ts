const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || '';

export function createLink(url: string) {
    const crafted_url = `${BASE_PATH}${url}`;
    return crafted_url;
}
