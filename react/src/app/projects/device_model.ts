
// This file contains classes for available MCD device types. The interfaces are modelled after the 
// 'type_validator' on the backend.
// 
// NOTE: typescript does not support multiple inheritance so we can't model a device type by 
// inheriting fields from multiple classes. For this reason we do the following:
// 
//  * every supported device inherits from DeviceMcd (base class) in order to inherit the common device fields
//  * the rest of the fields are inherited by implementing the common 'RTD' interfaces
//
// This leads to repetition of empty field declarations for every new class we create. The benefit,
// however is typesafety within our UI code (ability to do class casting and never reach for a field
// that doesn't exist for a specific type)


// determines a device type: this enum should be kept in sync with the backend enum
// NOTE: none of these types should be reused. If a device type is no longer used / deprecated
// and a new one created, we should use a different enum.
export enum DeviceType {
    UNSET = 0,
    UNKNOWN = 1,
    MCD = 2,
    SOURCE = 3,
    BLANK = 4,
    APERTURE = 5,
    FLAT_MIRROR = 6,
    KB_MIRROR = 7,
    CRL = 8,
    CRYSTAL = 9,
    GRATING = 10,
    GROUP = 11,
}

// parse a device object from a provided json object. This lets us be typesafe in our ui code
export function parseDevice(deviceObj: Record<string, any>): DeviceMcd {
    let deviceType = deviceObj.get('device_type')
    if (deviceType === undefined) {
        throw new Error(`failed to parse a device: invalid json object: missing 'device_type' field: original object: ${JSON.stringify(deviceObj)}`)
    }

    if (typeof deviceType != "number") {
        throw new Error(`failed to parse a device: device type field is not a number: original object: ${JSON.stringify(deviceObj)}`)
    }

    switch (deviceType) {
        case DeviceType.UNSET, DeviceType.UNKNOWN: {
            let d = new DeviceMcd();
            Object.assign(d, deviceObj);
            return d
        }
        case DeviceType.MCD: {
            return Object.assign(new DeviceMcd(), deviceObj);
        }
        case DeviceType.FLAT_MIRROR: {
            return Object.assign(new DeviceFlatMirror(), deviceObj);
        }
        case DeviceType.KB_MIRROR: {
            return Object.assign(new DeviceKbMirror(), deviceObj);
        }
        case DeviceType.GROUP: {
            return Object.assign(new DeviceGroup(), deviceObj);
        }
        // TODO: write the rest of the cases...
        default:
            // this should never happen
            throw new Error(`failed to parse a device: unhandled device type ${deviceType}`)
    }
}

// base device for every supported MCD device
class DeviceMcd {
    // device metadata
    _id: string = "";          // mongodb document_id 
    device_id: string = "";    // internal uuid so we know can uniquely locate a device
    device_type: number = 0;  // depending on the type of a device may have different fields
    created: Date = new Date(0);

    // mcd fields (all devices have them)
    fc: string = "";
    fg: string = "";

    fg_desc: string = "";  // deprecated field ? 
    tc_part_no: string = "";
    state: string = "";
    stand: string = "";
    comment: string = "";
    location: string = "";
    beamline: string = "";

    nom_ang_x?: number;
    nom_ang_y?: number;
    nom_ang_z?: number;
    nom_loc_x?: number;
    nom_loc_y?: number;
    nom_loc_z?: number;

    ray_trace?: number;

    discussion: ChangeComment[] = [];
}

// used for displaying comment threads
export interface ChangeComment {
    id: string;
    author: string;
    created: Date;
    comment: string;
}

export class DeviceSource extends DeviceMcd {
    // TODO: add missing fields
}

export class DeviceBlank extends DeviceMcd {
    // TODO: add missing fields
}

export class DeviceAperture extends DeviceMcd {
    // TODO: add missing fields
}

export class DeviceCrl extends DeviceMcd {
    // TODO: add missing fields
}

export class DeviceCrystal extends DeviceMcd {
    // TODO: add missing fields
}

export class DeviceGrating extends DeviceMcd {
    // TODO: add missing fields
}

// TODO: this is the default value of a number, but if the number is not set should we made it 
// an optional type instead?
const DEFAULT_NUM = NaN;


export class DeviceFlatMirror extends DeviceMcd implements _mirror_geometry_fields, _motion_range_fields, _tolerance_fields {
    // geometry fields
    geom_len: number = DEFAULT_NUM;
    geom_width: number = DEFAULT_NUM;
    thickness: number = DEFAULT_NUM;
    geom_center_x: number = DEFAULT_NUM;
    geom_center_y: number = DEFAULT_NUM;
    geom_center_z: number = DEFAULT_NUM;

    // motion fields
    motion_min_x: number = DEFAULT_NUM;
    motion_max_x: number = DEFAULT_NUM;
    motion_min_y: number = DEFAULT_NUM;
    motion_max_y: number = DEFAULT_NUM;
    motion_min_z: number = DEFAULT_NUM;
    motion_max_z: number = DEFAULT_NUM;
    motion_min_rx: number = DEFAULT_NUM;
    motion_max_rx: number = DEFAULT_NUM;
    motion_min_ry: number = DEFAULT_NUM;
    motion_max_ry: number = DEFAULT_NUM;
    motion_min_rz: number = DEFAULT_NUM;
    motion_max_rz: number = DEFAULT_NUM;

    // tolerance fields
    tolerance_x: number = DEFAULT_NUM;
    tolerance_y: number = DEFAULT_NUM;
    tolerance_z: number = DEFAULT_NUM;
    tolerance_rx: number = DEFAULT_NUM;
    tolerance_ry: number = DEFAULT_NUM;
    tolerance_rz: number = DEFAULT_NUM;
}


export class DeviceKbMirror extends DeviceFlatMirror implements _mirror_geometry_fields, _motion_range_fields, _tolerance_fields {
    focus_min_p: number = DEFAULT_NUM;
    focus_max_p: number = DEFAULT_NUM;
    focus_min_q: number = DEFAULT_NUM;
    focus_max_q: number = DEFAULT_NUM;
    focus_theta: number = DEFAULT_NUM;
}

export class DeviceGroup extends DeviceMcd {
    subdevices: DeviceMcd[] = [];
}


// ------------------- common interfaces that multiple devices may share --------------------


interface _geometry_center_fields {
    geom_center_x: number;
    geom_center_y: number;
    geom_center_z: number;
}

interface _mirror_geometry_fields extends _geometry_center_fields {
    geom_len: number;
    geom_width: number;
    thickness: number;
}

interface _motion_range_fields {
    motion_min_x: number;
    motion_max_x: number;
    motion_min_y: number;
    motion_max_y: number;
    motion_min_z: number;
    motion_max_z: number;


    motion_min_rx: number;
    motion_max_rx: number;
    motion_min_ry: number;
    motion_max_ry: number;
    motion_min_rz: number;
    motion_max_rz: number;
}

interface _tolerance_fields {
    tolerance_x: number;
    tolerance_y: number;
    tolerance_z: number;

    tolerance_rx: number;
    tolerance_ry: number;
    tolerance_rz: number;
}