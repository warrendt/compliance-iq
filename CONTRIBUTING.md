# Contributing to ComplianceIQ

Thank you for your interest in contributing! This project welcomes contributions from the community.

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/warrendt/compliance-iq/issues) to report bugs or request features
- Include steps to reproduce, expected behavior, and actual behavior
- For security vulnerabilities, please report privately via GitHub Security Advisories

### Adding or Updating Compliance Frameworks

1. Fork the repository
2. Add your catalog CSV to `catalogues/` following the existing 10-column format:
   - Control ID, Domain, Control Name, Requirement Summary, Control Type
   - Evidence Examples, Azure Policy Name, Azure Policy ID, Defender Category, Defender Recommendation
3. Add the source PDF to `reference_documents/` if publicly available
4. Update `catalogues/CATALOG_SUMMARY.md` with framework details
5. Submit a pull request

### Code Changes

1. Fork the repository and create a feature branch
2. Make your changes in the `app/` directory
3. Test locally:
   ```bash
   cd app/backend && pip install -r requirements.txt && uvicorn app.main:app --reload
   cd app/frontend && pip install -r requirements.txt && streamlit run 1_🏠_Home.py
   ```
4. Submit a pull request with a clear description

### Documentation

Improvements to documentation are always welcome. Update the relevant `.md` files and submit a PR.

## Code of Conduct

Be respectful and constructive in all interactions. We follow the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
