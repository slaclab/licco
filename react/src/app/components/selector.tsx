import { Button, Colors, ControlGroup, FormGroup, HTMLSelect } from "@blueprintjs/core";
import { useEffect, useState } from "react";
import { sortString } from "../utils/sort_utils";

interface selectorProps<T> {
    availableItems: T[],
    defaultSelectedItems?: T[],
    defaultValue: T,
    noSelectionMessage?: string | React.ReactNode;
    renderer: (element: T) => string;
    onChange?: (currentSelection: T[]) => void;
    disabled?: boolean;
}


// a dropdown with a list of selected items underneath (that could be removed as well)
export const MultiChoiceSelector = <T,>({ availableItems: allSelections, defaultSelectedItems, defaultValue, renderer, onChange, noSelectionMessage = '', disabled: disableActions = false }: selectorProps<T>) => {
    const [currentSelection, setCurrentSelection] = useState(defaultValue);
    const [selectedItems, setSelectedItems] = useState<T[]>(defaultSelectedItems || []);

    const [availableItems, setAvailableItems] = useState<T[]>([defaultValue]);
    const [availableItemsStrings, setAvailableItemsStrings] = useState<string[]>([]);

    useEffect(() => {
        const availItems = [defaultValue, ...allSelections.filter(e => !selectedItems.includes(e))];
        const availItemsString = availItems.map(e => renderer(e));

        if (availItems.length == 1 && availItems[0] == defaultValue) {
            // current selection is necessary to reset to default value in this edge case, otherwise
            // it would keep cached the previously selected value and the add button would be enabled.
            // This correctly disables the add button.
            setCurrentSelection(defaultValue);
        }
        setAvailableItems(availItems);
        setAvailableItemsStrings(availItemsString);
    }, [defaultValue, allSelections, selectedItems])


    const setCurrentSelectionViaIndex = (index: number) => {
        if (index > availableItems.length - 1) {
            if (availableItems.length > 0) {
                const current = availableItems[availableItems.length - 1]
                setCurrentSelection(current);
            } else {
                setCurrentSelection(defaultValue);
            }
            return;
        }
        setCurrentSelection(availableItems[index]);
    }

    const removeItem = (index: number) => {
        if (index < 0) {
            return index;
        }

        selectedItems.splice(index, 1)
        const updatedItems = [...selectedItems];

        setSelectedItems(updatedItems);
        onChange?.(updatedItems);
    }

    const addItem = (item: T) => {
        let index = availableItems.indexOf(item);
        if (index == availableItems.length - 1) {
            // user is set as last element, find previous index
            index--;
        } else {
            index++;
        }

        if (index >= 0 && index <= availableItems.length - 1) {
            setCurrentSelection(availableItems[index])
        } else {
            setCurrentSelection(defaultValue);
        }

        let updatedItems = [...selectedItems, item];
        updatedItems.sort((a, b) => sortString(renderer(a), renderer(b), false));

        setSelectedItems(updatedItems);
        onChange?.(updatedItems);
    }

    const renderSelection = () => {
        if (selectedItems.length == 0) {
            if (typeof (defaultValue) == 'string') {
                return <p style={{ color: Colors.GRAY1 }}>{noSelectionMessage}</p>
            }
            return noSelectionMessage;
        }

        return (
            <ul className="list-unstyled">
                {selectedItems.map((item, i) => {
                    return <li key={i}>
                        <ControlGroup>
                            <Button icon="cross" small={true} minimal={true}
                                disabled={disableActions}
                                onClick={(e) => removeItem(i)} />
                            {renderer(item)}
                        </ControlGroup>
                    </li>
                })}
            </ul>
        )
    }

    return (
        <FormGroup inline={false} className="m-0">
            <ControlGroup>
                <HTMLSelect
                    iconName="caret-down"
                    value={renderer(currentSelection)}
                    options={availableItemsStrings}
                    autoFocus={true}
                    disabled={disableActions}
                    onChange={(e) => setCurrentSelectionViaIndex(e.target.selectedIndex)}
                />
                <Button icon="add"
                    disabled={currentSelection === defaultValue || disableActions}
                    onClick={e => addItem(currentSelection)}>
                    Add
                </Button>
            </ControlGroup>
            {renderSelection()}
        </FormGroup>
    )
}
