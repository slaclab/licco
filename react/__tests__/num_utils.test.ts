import { numberOrDefault } from '@/app/utils/num_utils';
import { expect, test } from '@jest/globals';

test('number_or_default_parsing', () => {
    let a = 123;
    let b = 123.123;
    let c = 0;

    expect(numberOrDefault(a, undefined)).toBe(123);
    expect(numberOrDefault(b, undefined)).toBe(123.123);
    expect(numberOrDefault(c, undefined)).toBe(0);
});

test('number_or_default_parsing_string', () => {
    let a = '';
    let b = '123';
    let c = '0';
    let d = undefined;

    expect(numberOrDefault(a, undefined)).toBe(undefined);
    expect(numberOrDefault(b, undefined)).toBe(123);
    expect(numberOrDefault(c, undefined)).toBe(0);
    expect(numberOrDefault(d, undefined)).toBe(undefined);
});