const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatToLiccoDateTime(date?: Date): string {
    if (!date) {
        return "";
    }

    const day = date.getDate().toString().padStart(2, '0');
    const month = months[date.getMonth()];
    const year = date.getFullYear();

    const hours = date.getHours().toString().padStart(2, '0'); // Hours (24-hour format)
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');

    return `${month}/${day}/${year} ${hours}:${minutes}:${seconds}`;
}

export function formatToLiccoDate(date: Date): string {
    const day = date.getDate().toString().padStart(2, '0');
    const month = months[date.getMonth()];
    const year = date.getFullYear();
    return `${month}/${day}/${year}`;
}

export function toUnixMilliseconds(date: Date): number {
    return date.getTime();
}

export function toUnixSeconds(date: Date): number {
    return Math.round(date.getTime() / 1000);
}

export function toIsoDate(date: Date): string {
    const year = date.getFullYear()
    let m = date.getMonth() + 1;
    const month = `${m}`.padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function setStartOfDayHours(date: Date) {
    date.setHours(0, 0, 0, 0);
}

function setEndOfDayHours(date: Date) {
    date.setHours(23, 59, 59, 999);
}

export function setTimeBoundary(date: Date, time: "startDay" | "endDay"): Date {
    if (time == "startDay") {
        let d = new Date(date);
        setStartOfDayHours(d);
        return d;
    }

    let d = new Date(date);
    setEndOfDayHours(d);
    return d;
}

export function constructTimeBoundaries(now: Date, choice: "lastWeek" | "lastMonth" | "lastYear") {
    const end = setTimeBoundary(now, "endDay");

    switch (choice) {
        case "lastWeek": {
            let start = new Date(end);
            // start is now (today) - 6 days for a total of 7 days
            start.setHours(start.getHours() - 6 * 24);
            start = setTimeBoundary(start, "startDay")
            return { start, end };
        }
        case "lastMonth": {
            let day = now.getDate();
            let month = now.getMonth() - 1;
            let year = now.getFullYear();
            if (month < 0) {
                month = 11;
                year -= 1;
            }
            let start = setTimeBoundary(new Date(year, month, day), "startDay");
            return { start, end }
        }
        case "lastYear": {
            let year = now.getFullYear() - 1;
            let month = now.getMonth();
            let day = now.getDate();
            let start = new Date(year, month, day);
            start = setTimeBoundary(start, "startDay");
            return { start, end }
        }
    }
}
