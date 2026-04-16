# Contributing to Frappe Assistant Core

Welcome to Frappe Assistant Core! We're excited that you're interested in contributing to this open-source AGPL-3.0-licensed project. This guide will help you get started with contributing code, documentation, bug reports, and feature requests.

## 🌟 How You Can Contribute

### 🐛 Bug Reports
Found a bug? Help us fix it!
- **Search existing issues** first to avoid duplicates
- **Use our bug report template** when creating new issues
- **Include detailed information**: steps to reproduce, expected vs actual behavior
- **Provide environment details**: Frappe version, Python version, OS, etc.

### ✨ Feature Requests
Have an idea for a new feature?
- **Check the roadmap** and existing feature requests
- **Create a detailed proposal** with use cases and benefits
- **Be open to feedback** and discussion

### 🔧 Code Contributions
Ready to write some code?
- **Start with good first issues** labeled `good-first-issue`
- **Fork the repository** and create a feature branch
- **Follow our coding standards** (detailed below)
- **Add tests** for new functionality
- **Update documentation** for any changes
- **Submit a pull request** with a clear description

### 📚 Documentation Improvements
Help us improve our docs!
- **Fix typos and errors**
- **Add examples and use cases**
- **Improve clarity and structure**

## 🚀 Getting Started

### Prerequisites
- **Frappe Framework** v15+
- **Python** 3.11+
- **Git** for version control
- **Basic knowledge** of Frappe development

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/frappe-assistant-core.git
   cd frappe-assistant-core
   ```

2. **Install in Development Mode**
   ```bash
   # In your Frappe bench directory
   bench get-app frappe_assistant_core /path/to/your/cloned/repo
   bench --site your-dev-site install-app frappe_assistant_core
   ```

3. **Create Development Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 📝 Coding Standards

### Python Code Style
- **Follow PEP 8** for Python code formatting
- **Use meaningful variable names** and add comments for complex logic
- **Add docstrings** for all classes and functions
- **Keep functions small** and focused on single responsibilities

### Frappe Conventions
- **Follow Frappe naming conventions** for DocTypes and fields
- **Use Frappe utilities** instead of reinventing functionality
- **Respect Frappe permissions** and security patterns
- **Handle errors gracefully** with proper logging

## 📋 Pull Request Process

### Before Submitting
1. **Ensure your code follows our standards**
2. **Run all tests and ensure they pass**
3. **Update documentation if needed**
4. **Test your changes manually**
5. **Rebase your branch on latest main**

## 📄 License

By contributing to Frappe Assistant Core, you agree that your contributions will be licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. This means:

- ✅ **Your contributions are free** for everyone to use, modify, and distribute
- ✅ **No copyright assignment required** — you retain copyright of your contributions
- ⚠️ **Copyleft**: derivative works must also be AGPL-3.0 licensed
- ⚠️ **Network use provision**: providing the software as a service over a network requires source-code access for users
- ✅ **AGPL-3.0 applies** to all contributions

## 📞 Communication

### Getting Help
- **GitHub Discussions**: For questions and general discussion
- **GitHub Issues**: For bug reports and feature requests
- **Email**: [jypaulclinton@gmail.com](mailto:jypaulclinton@gmail.com) for private matters

### Community Guidelines
- **Be respectful** and inclusive
- **Provide constructive feedback**
- **Help others learn** and grow

## 🎉 Recognition

We value all contributions! Contributors will be:
- **Listed in our CONTRIBUTORS.md** file
- **Mentioned in release notes** for significant contributions
- **Invited to join** the contributors team (for regular contributors)

## 🚀 What's Next?

Ready to contribute? Here's how to start:

1. **⭐ Star the repository** to show your support
2. **🍴 Fork the repository** to your GitHub account
3. **📖 Read the documentation** to understand the project
4. **🔍 Browse open issues** to find something to work on
5. **💬 Join the discussion** in GitHub Discussions
6. **🛠️ Make your first contribution**

Thank you for contributing to Frappe Assistant Core! Together, we're building the future of AI-powered ERP systems. 🚀

---

**Questions?** Feel free to reach out via [GitHub Discussions](hhttps://github.com/buildswithpaul/Frappe_Assistant_Core/discussions) or email [jypaulclinton@gmail.com](mailto:jypaulclinton@gmail.com).