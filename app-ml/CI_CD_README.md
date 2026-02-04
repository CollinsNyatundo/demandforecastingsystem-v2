# CI/CD Automation for Demand Forecasting

This document describes the comprehensive CI/CD pipeline implemented for the demand forecasting system.

## 🚀 Overview

The CI/CD pipeline ensures code quality, security, and reliability through automated checks and validations on every push and pull request.

## 📋 Pipeline Stages

### 1. Code Quality Checks
- **Ruff Linter**: Fast Python linting and formatting
- **Ruff Formatter**: Consistent code formatting
- **MyPy**: Static type checking
- **Bandit**: Security vulnerability scanning
- **Safety**: Dependency vulnerability checking

### 2. Testing
- **Unit Tests**: Comprehensive test suite with coverage reporting
- **Data Validation**: Pipeline data integrity checks
- **Integration Tests**: End-to-end system testing with MinIO

### 3. Security
- **Trivy**: Container and file system vulnerability scanning
- **Security Reports**: Automated security artifact generation

### 4. Build
- **Docker Build**: Validates container builds on main branch
- **Build Caching**: Optimized builds with GitHub Actions cache

## 🛠️ Local Development Setup

### Prerequisites
- Python 3.10+
- Git
- Docker (for integration tests)

### Quick Setup

1. **Run the setup script:**
   ```bash
   cd app-ml
   chmod +x setup_ci.sh
   ./setup_ci.sh
   ```

2. **Manual setup (alternative):**
   ```bash
   # Install dependencies
   pip install -e ".[dev]"
   pip install pre-commit safety trivy
   
   # Set up pre-commit hooks
   pre-commit install
   pre-commit install --hook-type commit-msg
   ```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality before commits:

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run hooks on staged files
pre-commit run

# Skip a specific hook (if needed)
pre-commit run --skip-hook bandit
```

## 📊 CI/CD Workflow

### Triggers
- **Push to main/develop**: Full pipeline execution
- **Pull Request**: Full pipeline execution
- **Main branch**: Additional Docker build step

### Job Dependencies
```
lint → test → integration → build (main only)
data-validation (parallel)
security (parallel)
```

### Coverage Requirements
- **Minimum Coverage**: 80%
- **Coverage Reports**: XML and terminal output
- **Codecov Integration**: Automatic coverage reporting

## 🔧 Configuration Files

### `.github/workflows/ci.yml`
Main CI/CD pipeline configuration with:
- Multi-stage validation
- Parallel execution where possible
- Artifact collection and reporting
- Docker build validation

### `.pre-commit-config.yaml`
Local development quality gates:
- Code formatting and linting
- Type checking
- Security scanning
- File quality checks

### `pyproject.toml`
Project configuration with:
- Development dependencies
- Tool configurations
- Build settings

## 📈 Quality Metrics

The pipeline enforces the following quality standards:

### Code Quality
- **Zero Ruff violations**: Code must pass all linting rules
- **Consistent formatting**: Automatic formatting enforcement
- **Type safety**: MyPy type checking (warnings allowed initially)

### Security
- **Zero high-severity vulnerabilities**: Bandit security checks
- **Dependency scanning**: Safety vulnerability checks
- **Container security**: Trivy vulnerability scanning

### Testing
- **80% minimum coverage**: Enforced test coverage
- **All tests must pass**: No failing tests allowed
- **Integration validation**: End-to-end system testing

## 🚨 Troubleshooting

### Common Issues

1. **Pre-commit hook failures:**
   ```bash
   # Re-run hooks after fixing issues
   pre-commit run --all-files
   ```

2. **CI failures:**
   - Check the GitHub Actions logs for specific error details
   - Look for security scan reports in artifacts
   - Review coverage reports for missing tests

3. **Docker build failures:**
   - Ensure Dockerfile exists and is valid
   - Check build context and file paths
   - Review build logs for specific errors

### Debugging Tips

- **Local testing**: Run `pre-commit run --all-files` before pushing
- **Coverage reports**: Check `coverage.xml` for detailed coverage info
- **Security reports**: Review `bandit-report.json` and `safety-report.json`
- **Integration tests**: Ensure MinIO service is running locally

## 📚 Best Practices

### Development Workflow
1. Create feature branch from develop
2. Make changes with frequent commits
3. Run pre-commit hooks locally
4. Create pull request to develop
5. Address any CI/CD failures
6. Merge after approval

### Code Quality
- Write tests for new functionality
- Maintain 80%+ test coverage
- Follow type hints best practices
- Address security warnings promptly

### Security
- Never commit secrets or credentials
- Use environment variables for sensitive data
- Regularly update dependencies
- Review security scan reports

## 🔗 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Pre-commit Documentation](https://pre-commit.com/)
- [Bandit Security Scanner](https://bandit.readthedocs.io/)
- [Safety Dependency Checker](https://pyup.io/safety/)

---

**Status**: ✅ Active and Enforced  
**Last Updated**: February 4, 2026  
**Maintainers**: Development Team
