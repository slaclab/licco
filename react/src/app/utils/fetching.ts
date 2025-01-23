
export const HOSTNAME = process.env.NEXT_PUBLIC_BACKEND_URL;
const NO_CONTENT = 204;
const FORBIDDEN = 403;
const UNAUTHORIZED = 401;
const INVALID_JSON = 500;
const FETCH_FAILED = 500;

// json error message that comes from backend
export interface JsonErrorMsg {
    error: string;
    code: number;
}

interface LiccoError {
    errormsg?: string
}

export class Fetch {
    static get<T>(url: string, options: any = {}): Promise<T> {
        options["method"] = "GET";
        return Fetch.fetchHelper(url, options)
    }

    static post<T>(url: string, options: any = {}): Promise<T> {
        options["method"] = "POST";
        return Fetch.fetchHelper(url, options)
    }

    static delete<T>(url: string, options: any = {}): Promise<T> {
        options["method"] = "DELETE";
        return Fetch.fetchHelper(url, options)
    }

    static put<T>(url: string, options: any = {}): Promise<T> {
        options["method"] = "PUT";
        return Fetch.fetchHelper(url, options)
    }

    static getCookie(name: string): string {
        let cookieValue = "";
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    static async fetchHelper<T>(path: string, config?: any): Promise<T> {
        if (!config) {
            config = {};
        }

        if (!config["headers"]) {
            config["headers"] = {};
        }

        if (config["headers"]["Content-Type"] == undefined) {
            config["headers"]["Content-Type"] = "application/json";
        } else if (config["headers"]["Content-Type"] === "MULTIPART") {
            // Let the browser set it's own headers, this is currently
            // only used when sending multipart form, because for some reason
            // quarkus doesn't like custom Content-Type: "multipart-form".
            delete config["headers"]["Content-Type"];
        }

        if (config["headers"]["Accept"] == undefined) {
            config["headers"]["Accept"] = "application/json";
        }

        // has to be include, otherwise we can't send credentials/cookies 
        // to a server that is on a different domain
        // (e.g., localhost:9000 instead of localhost:3000)
        // config["credentials"] = "include";

        let response;
        try {
            response = await fetch(HOSTNAME + path, config)
        } catch (e) {
            // failed to fetch
            let errorMessage = "Failed to fetch response for " + HOSTNAME + path;
            if (e instanceof Error) { // we have to do this to be able to access e.message
                errorMessage += ": " + e.message;
            }
            return new Promise((_, reject) => reject({ error: errorMessage, code: FETCH_FAILED }));
        }

        if (response.ok) {
            if (config["headers"]["Accept"] !== "application/json") {
                return response.blob() as T;
            }

            if (response.status == NO_CONTENT) {
                // sometimes the response will be empty (usually a delete respone) in which case
                // we don't have anything to return but undefined to satisfy the generic type T
                let t: T;
                return new Promise(ok => ok(t));
            }

            // fetch text from response
            let text: string = "";
            try {
                text = await response.text();
            } catch (e) {
                let errorMessage = "Failed to read response for " + HOSTNAME + path;
                if (e instanceof Error) {
                    errorMessage += ": " + e.message;
                }
                let errMsg: JsonErrorMsg = { 'error': errorMessage, code: INVALID_JSON };
                return new Promise((_, err) => err(errMsg));
            }

            // NOTE: when parsing an empty string '' as json, it will throw a json parse error.
            // This should never happen since the backend should always return either {} or []
            // If this edge case happens, however, we still have to handle it
            if (text == "") {
                let errMsg: JsonErrorMsg = { error: 'Server returned an empty string, which is not a valid json', code: INVALID_JSON };
                return new Promise((_, reject) => reject(errMsg))
            }

            // try to parse text as a json response
            try {
                let data = JSON.parse(text) as T;
                return new Promise(ok => ok(data));
            } catch (e) {
                // failed to parse json.
                let errorMessage = "Failed to parse response to " + HOSTNAME + path + " as JSON";
                if (e instanceof Error) {
                    errorMessage += ": " + e.message;
                }
                errorMessage += "\nOriginal Response:\n" + text;
                let errMsg: JsonErrorMsg = { error: errorMessage, code: INVALID_JSON };
                return new Promise((_, errResponse) => errResponse(errMsg));
            }
        }

        // we received an error, parse it
        try {
            let errJson = await response.json() as LiccoError;
            let msg = errJson.errormsg || `There was an error when making a request for ${HOSTNAME}${path}`;
            let e: JsonErrorMsg = { error: msg, code: response.status }
            return new Promise((_, err) => err(e));
        } catch (e) {
            // failed to parse response as json
            let errMsg: JsonErrorMsg = { 'error': response.statusText, code: response.status };
            return new Promise((_, errResponse) => errResponse(errMsg));
        }
    }
}