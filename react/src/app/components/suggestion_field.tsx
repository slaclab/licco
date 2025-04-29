import { MenuItem } from "@blueprintjs/core"
import { ItemPredicate, ItemRenderer, Suggest, SuggestProps } from "@blueprintjs/select"
import { useCallback } from "react";

type Modify<T, R> = Omit<T, keyof R> & R;

type StringSuggestProps = Modify<SuggestProps<string>, { 
    // provide a unified value prop instead of separating query and selection
    value: string, 
    setValue: (value: string) => void,

    // make certain previously required fields optional and provide defaults instead
    inputValueRenderer?: (item: string) => string,
    itemRenderer?: ItemRenderer<string>,
    onItemSelect?: (item: string, event?: React.SyntheticEvent<HTMLElement>) => void
}>

type NewItemRenderer = (query: string, active: boolean, handleClick: React.MouseEventHandler<HTMLElement>) => React.JSX.Element | undefined

/*
Extends the functionality of the Suggest component from @blueprintjs/select with defaults reasonable for working directly with strings.
*/
export const StringSuggest: React.FC<StringSuggestProps> = (props) => {
    const {value, setValue} = props
    
    const renderItem: ItemRenderer<string> =  useCallback((item, rendererProps) => {
        if (!rendererProps.modifiers.matchesPredicate) {
            return null;
        }
        return <MenuItem
            text={item}
            roleStructure="listoption"
            active={rendererProps.modifiers.active}
            onClick={rendererProps.handleClick}
            selected={item === value}
        />
    }, [value])
    
    const renderNewItem: NewItemRenderer  = useCallback((item, active, handleClick) => (
        <MenuItem
            icon="add"
            text={item}
            roleStructure="listoption"
            active={active}
            onClick={handleClick}
        />
    ), [value])
    
    const filter: ItemPredicate<string> = useCallback((query, item, _index, exactMatch) => {
        const normalizedItem = item.toLowerCase()
        const normalizedQuery = query.toLowerCase()
        if (exactMatch) {
            return normalizedItem === normalizedQuery
        } else {
            return normalizedItem.includes(normalizedQuery)
        }
    }, [])
    
    return <Suggest 
        query={value}
        inputValueRenderer={(item) => item}
        itemRenderer={renderItem}
        onItemSelect={setValue}
        itemPredicate={filter}

        createNewItemFromQuery={(query) => query}
        createNewItemRenderer={renderNewItem}
        createNewItemPosition="first"

        popoverProps={{minimal: true}}

        {...props}
    />
}