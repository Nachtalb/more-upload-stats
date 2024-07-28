#!/bin/sh
set -eu

# Color codes
RED_BG='\033[41m'
GREEN_BG='\033[42m'
YELLOW_BG='\033[43m'
BLUE_BG='\033[44m'
MAGENTA_BG='\033[45m'
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

# Function to generate changelog
generate_changelog() {
    if [ -f "./generate_changelog.py" ]; then
        print_color "$BLUE_BG" "INFO:" "Generating changelog..."
        if ./generate_changelog.py; then
            print_color "$GREEN_BG" "SUCCESS:" "Changelog generated successfully."
        else
            print_color "$RED_BG" "ERROR:" "Failed to generate changelog. Exiting."
            exit 1
        fi
    else
        print_color "$MAGENTA_BG" "SKIP:" "generate_changelog.py not found. Skipping changelog generation."
    fi
}

# Function to preview version bump and get confirmation
preview_and_confirm_bump() {
    print_color "$BLUE_BG" "PREVIEW:" "Dry run of version bump with flag: $1"
    poetry version --next-phase "$1" --dry-run
    if get_confirmation "Do you want to proceed with this version bump?"; then
        poetry version --next-phase "$1"
        print_color "$GREEN_BG" "SUCCESS:" "Version bumped."
        return 0
    else
        print_color "$RED_BG" "ABORT:" "Version bump cancelled."
        return 1
    fi
}

# Function to update PLUGININFO
update_pluginfile() {
    local new_version="$1"
    if [ -f "PLUGININFO" ]; then
        print_color "$BLUE_BG" "INFO:" "Updating PLUGININFO..."
        sed -i "s/Version=\".*\"/Version=\"$new_version\"/" PLUGININFO
        print_color "$GREEN_BG" "SUCCESS:" "PLUGININFO updated."
    else
        print_color "$MAGENTA_BG" "SKIP:" "PLUGININFO not found. Skipping PLUGININFO update."
    fi
}

# Function to show changes and commit
show_and_commit_changes() {
    local flag="$1"
    print_color "$CYAN_BG" "DIFF:" "Showing changes:"
    git_diff_staged_command="git --no-pager diff --staged"
    git_diff_command="git --no-pager diff pyproject.toml"
    git_add_command="git add pyproject.toml"

    if [ -f "CHANGELOG.rst" ]; then
        git_diff_command="$git_diff_command CHANGELOG.rst"
        git_add_command="$git_add_command CHANGELOG.rst"
    fi

    if [ -f "PLUGININFO" ]; then
        git_diff_command="$git_diff_command PLUGININFO"
        git_add_command="$git_add_command PLUGININFO"
    fi

    $git_diff_staged_command
    $git_diff_command

    if get_confirmation "Do you want to commit these changes?"; then
        current_version=$(poetry version -s)
        $git_add_command
        git commit -m "Bump version to $current_version and update changelog"
        case "$flag" in
            prepatch|preminor|premajor|prerelease)
                print_color "$YELLOW_BG" "INFO:" "Prerelease version detected. Skipping tag creation."
                ;;
            *)
                git tag -a "v$current_version" -m "Release version $current_version"
                print_color "$GREEN_BG" "SUCCESS:" "Changes committed and tagged as v$current_version."
                ;;
        esac
    else
        print_color "$RED_BG" "ABORT:" "Commit cancelled. Exiting."
        exit 1
    fi
}

# Function to push changes and tags
push_changes_and_tags() {
    if get_confirmation "Do you want to push these changes and tags?"; then
        git push && git push --tags
        print_color "$GREEN_BG" "SUCCESS:" "Changes and tags pushed."
    else
        print_color "$MAGENTA_BG" "SKIP:" "Push skipped. Continuing."
    fi
}

# Main script
main() {
    if [ $# -ne 1 ]; then
        print_color "$RED_BG" "ERROR:" "Invalid number of arguments."
        print_color "$CYAN_BG" "USAGE:" "$0 --<flag>"
        print_color "$CYAN_BG" "FLAGS:" "patch, minor, major, prepatch, preminor, premajor, prerelease"
        exit 1
    fi

    flag="${1#--}"
    initial_version=$(poetry version -s)

    generate_changelog

    case "$flag" in
        patch|minor|major|prepatch|preminor|premajor|prerelease)
            if preview_and_confirm_bump "$flag"; then
                update_pluginfile "$(poetry version -s)"
                show_and_commit_changes "$flag"
                push_changes_and_tags
            else
                exit 1
            fi
            ;;
        *)
            print_color "$RED_BG" "ERROR:" "Invalid flag: $flag"
            exit 1
            ;;
    esac

    print_color "$BLUE_BG" "INFO:" "Performing additional prepatch bump"
    if preview_and_confirm_bump prepatch; then
        update_pluginfile "$(poetry version -s)"
        show_and_commit_changes "prepatch"
        push_changes_and_tags
    else
        exit 1
    fi

    final_version=$(poetry version -s)
    print_color "$GREEN_BG" "COMPLETE:" "Version bumped from $initial_version to $final_version"
}

main "$@"
