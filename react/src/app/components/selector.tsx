import { Button, Colors, ControlGroup, FormGroup, HTMLSelect, MenuItem } from "@blueprintjs/core";
import { useEffect, useState } from "react";
import { sortString } from "../utils/sort_utils";

import { ItemPredicate, ItemRenderer, Suggest } from "@blueprintjs/select";
import React from "react";

interface selectorProps<T> {
    availableItems: T[],
    defaultSelectedItems?: T[],
    defaultValue: T,
    placeholder?: T,
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
            if (typeof (noSelectionMessage) == 'string') {
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


// an input box that also acts as a dropdown of predefined items
export const MultiChoiceStringSelector: React.FC<{ availableItems: string[], defaultSelectedItems: string[], defaultValue?: string, placeholder: string, onChange: (selectedItems: string[]) => void, noSelectionMessage: string, disabled?: boolean }>
    = ({ availableItems, defaultSelectedItems, defaultValue = "", placeholder = "", onChange, noSelectionMessage, disabled = false }) => {
        const [currentChoiceText, setCurrentChoiceText] = useState(defaultValue);
    const [selectedItems, setSelectedItems] = useState<string[]>(defaultSelectedItems || []);
    const [availableItemsStrings, setAvailableItemsStrings] = useState<string[]>([]);

    useEffect(() => {
        const availItems = [...availableItems.filter(e => !selectedItems.includes(e))];
        setAvailableItemsStrings(availItems);
    }, [defaultValue, availableItems, selectedItems])

    const removeItem = (index: number) => {
        if (index < 0) {
            return index;
        }

        selectedItems.splice(index, 1)
        const updatedItems = [...selectedItems];

        setSelectedItems(updatedItems);
        onChange?.(updatedItems);
    }

    const addItem = (item: string) => {
        if (!item) {
            return;
        }
        if (selectedItems.includes(item)) {
            return;
        }

        setCurrentChoiceText('');
        let updatedItems = [...selectedItems, item];
        updatedItems.sort((a, b) => sortString(a, b, false));
        setSelectedItems(updatedItems);
        onChange?.(updatedItems);
    }

    const renderSelection = () => {
        if (selectedItems.length == 0) {
            if (typeof (noSelectionMessage) == 'string') {
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
                                disabled={disabled}
                                onClick={(e) => removeItem(i)} />
                            {item}
                        </ControlGroup>
                    </li>
                })}
            </ul>
        )
    }

    return (
        <FormGroup inline={false} className="m-0">
            <ControlGroup>
                <Suggest<string>
                    items={availableItemsStrings}
                    itemPredicate={stringFilterItemPredicate} itemRenderer={stringItemRenderer}
                    noResults={undefined}
                    inputValueRenderer={e => e}
                    onItemSelect={(item) => setCurrentChoiceText(item)}
                    onQueryChange={e => setCurrentChoiceText(e)}
                    query={currentChoiceText}
                    inputProps={{
                        placeholder: placeholder ?? "Search...",
                        // NOTE: we can't use a keyup event handler for adding items via Enter key 
                        // as that would override the default behavior and keep the dropdown open
                        // after the enter click.
                        // (default behavior: if there is a dropdown, on enter the first suggestion
                        // will be selected)
                    }}
                    popoverProps={{
                        minimal: true,
                    }}
                    defaultSelectedItem={''}
                    selectedItem={''}
                    fill={false}
                />

                <Button icon="add"
                    disabled={disabled || !currentChoiceText || currentChoiceText === defaultValue || selectedItems.includes(currentChoiceText)}
                    onClick={e => addItem(currentChoiceText)}>
                    Add
                </Button>
            </ControlGroup>

            {renderSelection()}
        </FormGroup>
    )
}

const stringFilterItemPredicate: ItemPredicate<string> = (query, item, _index, exactMatch) => {
    // first check if the exact query was found
    if (item.indexOf(query) > 0) {
        return true
    }

    // query was not found, so we normalize the title and the query and check again
    const normalizedTitle = item.toLowerCase();
    const normalizedQuery = query.toLowerCase();
    if (exactMatch) {
        return normalizedTitle === normalizedQuery;
    } else {
        return normalizedTitle.indexOf(normalizedQuery) >= 0;
    }
};

const stringItemRenderer: ItemRenderer<string> = (item, { handleClick, handleFocus, modifiers, query }) => {
    if (!modifiers.matchesPredicate) {
        return null;
    }

    return (
        <MenuItem
            active={modifiers.active}
            disabled={modifiers.disabled}
            key={item}
            // label is part on the right side of the dropdown
            // label={item}
            onClick={handleClick}
            onFocus={handleFocus}
            roleStructure="listoption"
            text={item}
        />
    );
}
