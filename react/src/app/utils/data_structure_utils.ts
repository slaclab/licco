export function mapLen(map: Record<any, any> | Map<any, any>): number {
    if (map instanceof Map) {
        return map.size;
    }
    return Object.keys(map).length;
}