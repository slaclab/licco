
export function clamp(val: number, min: number, max: number): number {
    if (val < min) {
        return min;
    }
    if (val > max) {
        return max;
    }
    return val;
}


export function numberOrDefault(value: number | string | undefined, defaultVal: number | undefined): number | undefined {
    if (value === "" || value === undefined) {
        return undefined;
    }

    if (typeof value === "number") {
        return value;
    }

    let num = Number.parseFloat(value);
    if (isNaN(num)) {
        // this should never happen since we verify the fields before the user 
        // is able to submit them. 
        return defaultVal;
    }
    return num;
}
