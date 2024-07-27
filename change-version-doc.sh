#!/bin/sh
set -eu

# Color codes
RED_BG='\033[41m'
GREEN_BG='\033[42m'
YELLOW_BG='\033[43m'
BLUE_BG='\033[44m'
CYAN_BG='\033[46m'
BLACK='\033[30m'
RESET='\033[0m'

# Function to print colored messages
print_color() {
    printf "%b%s%b %s\n" "$1$BLACK" "$2" "$RESET" "$3"
}

# Function to get user confirmation
get_confirmation() {
    printf "%b%s%b %s" "$YELLOW_BG$BLACK" "$1" "$RESET" "[Y/n]: "
    read -r answer
    case "$answer" in
        [Nn]*)
            return 1
            ;;
        *)
            return 0
            ;;
    esac
}

# Function to update version numbers
update_versions() {
    old_version="$1"
    new_version="$2"

    print_color "$BLUE_BG" "INFO:" "Updating version numbers from $old_version to $new_version"

    # Use find to locate all files under ./npc
    find ./npc -type f -print0 | xargs -0 sed -i.bak \
        -e "s/\.\. versionchanged:: $old_version/.. versionchanged:: $new_version/g" \
        -e "s/\.\. versionadded:: $old_version/.. versionadded:: $new_version/g" \
        -e "s/\.\. versionremoved:: $old_version/.. versionremoved:: $new_version/g"

    print_color "$GREEN_BG" "SUCCESS:" "Version numbers updated"
}

# Function to show changes
show_changes() {
    print_color "$BLUE_BG" "INFO:" "Showing changes made:"
    git diff --color ./npc
}

# Main script
main() {
    if [ $# -ne 2 ]; then
        print_color "$RED_BG" "ERROR:" "Invalid number of arguments."
        print_color "$CYAN_BG" "USAGE:" "$0 <old_version> <new_version>"
        exit 1
    fi

    old_version="$1"
    new_version="$2"

    if get_confirmation "Update version from $old_version to $new_version?"; then
        update_versions "$old_version" "$new_version"
        show_changes

        if get_confirmation "Do you want to keep these changes?"; then
            find ./npc -name "*.bak" -type f -delete
            print_color "$GREEN_BG" "SUCCESS:" "Changes applied and backup files removed."
        else
            find ./npc -name "*.bak" -type f -exec sh -c 'mv "$1" "${1%.bak}"' _ {} \;
            print_color "$YELLOW_BG" "REVERT:" "Changes reverted using backup files."
        fi
    else
        print_color "$YELLOW_BG" "ABORT:" "Operation cancelled."
        exit 1
    fi
}

main "$@"
