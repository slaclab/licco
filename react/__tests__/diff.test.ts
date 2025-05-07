import { createFftDiff } from '@/app/projects/[projectId]/diff/project_diff_model';
import { DeviceState, ProjectDeviceDetails, ProjectInfo } from '@/app/projects/project_model';
import { expect, test } from '@jest/globals';

const createMockProjectInfo = (name: string) => {
    let p: ProjectInfo = { _id: name, name: name, creation_time: new Date(), owner: name, editors: [], description: "", status: "approved", notes: [] }
    return p;
}

const createdDevice = new Date();

const createMockDeviceDetails = (fc: string, fg: string) => {
    let d: ProjectDeviceDetails = {
        _id: '',
        fc: fc, fg: fg, area: '', beamline: [], state: DeviceState.Conceptual.name, tc_part_no: "", comments: "", stand: '', discussion: [],
        device_id: '', device_type: 2, created: createdDevice, project_id: ''
    }
    return d;
}

// tests if devices are properly grouped into "new", "missing", "updated", "identical" device groups
test('diff algorithm grouping', () => {
    let projectA = createMockProjectInfo("a");
    let projectB = createMockProjectInfo("b");

    // create devices for each project
    // 
    // We need to test:
    // 1. New device             (is in A, but not in B)
    // 2. Missing/deleted device (is not in A, but is in B)
    // 3. Updated device         (is in A and in B, but has some fields changed)
    // 4. Identical device       (is in A and in B with same data)

    let devicesA: ProjectDeviceDetails[] = [];
    {
        let newDevice = createMockDeviceDetails("A", "NEW_DEVICE");
        newDevice.nom_ang_x = 0.01

        let updatedDevice = createMockDeviceDetails("A", "UPDATED_DEVICE");
        updatedDevice.ray_trace = 0;

        let identicalDevice = createMockDeviceDetails("A", "IDENTICAL_DEVICE");
        identicalDevice.nom_ang_z = 1.2;

        devicesA.push(newDevice, updatedDevice, identicalDevice);
    }

    // B parts
    let devicesB: ProjectDeviceDetails[] = [];
    {
        let missingDevice = createMockDeviceDetails("B", "MISSING_DEVICE");
        missingDevice.nom_ang_x = 0.2;

        let updatedDevice = createMockDeviceDetails("A", "UPDATED_DEVICE");
        updatedDevice.ray_trace = 1;

        let identicalDevice = createMockDeviceDetails("A", "IDENTICAL_DEVICE");
        identicalDevice.nom_ang_z = 1.2;

        devicesB.push(missingDevice, updatedDevice, identicalDevice);
    }


    // create diff and check if the devices were properly grouped
    let diff = createFftDiff(projectA, devicesA, projectB, devicesB);

    expect(diff.a).toBe(projectA);
    expect(diff.b).toBe(projectB);


    { // check if found the right new device
        expect(diff.new.length).toBe(1);
        let newDevice = diff.new[0];
        expect(newDevice.fc).toBe("A");
        expect(newDevice.fg).toBe("NEW_DEVICE");
    }

    { // check if we found the right missing device
        expect(diff.missing.length).toBe(1);
        let missingDevice = diff.missing[0];
        expect(missingDevice.fc).toBe("B");
        expect(missingDevice.fg).toBe("MISSING_DEVICE");
        expect(missingDevice.nom_ang_x).toBe(0.2);
    }

    { // check if we found the right updated device
        expect(diff.updated.length).toBe(1);
        let updatedDevices = diff.updated[0];

        let updatedA = updatedDevices.a;
        expect(updatedA.fc).toBe("A");
        expect(updatedA.fg).toBe("UPDATED_DEVICE");
        expect(updatedA.ray_trace).toBe(0);

        let updatedB = updatedDevices.b;
        expect(updatedB.fc).toBe("A");
        expect(updatedB.fg).toBe("UPDATED_DEVICE");
        expect(updatedB.ray_trace).toBe(1);
    }

    { // check if we found the right identical device
        expect(diff.identical.length).toBe(1);
        let identicalDevice = diff.identical[0];
        expect(identicalDevice.fc).toBe("A");
        expect(identicalDevice.fg).toBe("IDENTICAL_DEVICE");
        expect(identicalDevice.nom_ang_z).toBe(1.2);
    }
})

// test if beamline array element change is correctly detected
test('diff beamline detection', () => {
    let projectA = createMockProjectInfo("a");
    let projectB = createMockProjectInfo("b");

    let devicesA: ProjectDeviceDetails[] = [];
    {
        let identicalDevice = createMockDeviceDetails("A", "IDENTICAL_DEVICE");
        identicalDevice.nom_ang_x = 0.01
        identicalDevice.beamline = ['AAA', 'BBB'];

        let updatedDevice = createMockDeviceDetails("B", "UPDATED_DEVICE");
        updatedDevice.beamline = ['AAA', 'BBB'];

        devicesA.push(identicalDevice, updatedDevice);
    }

    let devicesB: ProjectDeviceDetails[] = [];
    {
        let identicalDevice = createMockDeviceDetails("A", "IDENTICAL_DEVICE");
        identicalDevice.nom_ang_x = 0.01
        identicalDevice.beamline = ['AAA', 'BBB'];

        let updatedDevice = createMockDeviceDetails("B", "UPDATED_DEVICE");
        updatedDevice.beamline = ['AAA', 'CCC'];

        devicesB.push(identicalDevice, updatedDevice)
    }

    let diff = createFftDiff(projectA, devicesA, projectB, devicesB)
    { // check if we found identical device
        expect(diff.identical.length).toBe(1);
        let identicalDevice = diff.identical[0];
        expect(identicalDevice.fc).toBe("A");
        expect(["AAA", "BBB"])
        expect(identicalDevice.beamline).toEqual(["AAA", "BBB"]);
    }

    // check updated devices
    {
        expect(diff.updated.length).toBe(1);
        let updatedDevice = diff.updated[0];
        expect(updatedDevice.a.fc).toBe("B");
        expect(updatedDevice.b.fc).toBe("B");

        expect(updatedDevice.a.beamline).toEqual(["AAA", "BBB"]);
        expect(updatedDevice.b.beamline).toEqual(["AAA", "CCC"]);
    }
})