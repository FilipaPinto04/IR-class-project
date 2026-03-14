# TODO List

## High Priority
- [ ] Check if the Chrome binary path is valid before running
- [ ] Implement retry logic for transient failures (network issues, timeouts, etc.)
- [ ] Add config file for handle, max items, output file, etc.
- [ ] Own proposals for new features and improvements

## Features to Implement
- [ ] Futures based on https://github.com/maladeep/Coventry-PureHub-Search-Engine/tree/main?tab=readme-ov-file#features
- [ ] Write directly to JSON file while scraping to save memory on large collections
- [ ] Add Debug mode to enable/disable logging with print statements
- [ ] Implement graphical user interface (GUI) (using Tkinter or PyQt or web-based)
- [ ] Own proposals for new features and improvements

## Testing
- [ ] Write unit tests for the scraper class

## Dev Ops
- [ ] Add Colaborators to the repository, give Write access (allows creating branches and PRs)
- [ ] Enable Issues (to report bugs/ask questions)
- [ ] Set up issue templates and pull request templates for better collaboration
- [ ] Enable Discussions (for Q&A and announcements)
- [ ] Enable Wiki (for documentation)
- [ ] Set up CI/CD pipeline for automated testing and deployment
- [ ] Github Actions for automated testing on push and pull requests
- [ ] Require status checks to pass (if using GitHub Actions)
- [ ] Dockerize the application for easier deployment
- [ ] Set up Github Projects for task management
- [ ] Create detailed documentation for installation and usage
- [ ] Set up code coverage reporting
- [ ] Monitor performance and optimize as needed
- [ ] Github Releases for versioned distribution
- [ ] Own proposals for new features and improvements


## Notes
- Consider using a configuration library like `configparser` or `python-dotenv` for the config file
- For retry logic, consider using the `tenacity` library