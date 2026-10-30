"""Explicit one-time model installation. Translation itself stays offline."""
from .analyst import configure_argos


def main():
    configure_argos()
    import argostranslate.package
    if any(p.from_code == 'en' and p.to_code == 'pb'
           for p in argostranslate.package.get_installed_packages()):
        print('Modelo EN -> PT-BR já instalado.')
        return
    argostranslate.package.update_package_index()
    package = next(p for p in argostranslate.package.get_available_packages()
                   if p.from_code == 'en' and p.to_code == 'pb')
    argostranslate.package.install_from_path(package.download())
    print('Modelo EN -> PT-BR instalado. A tradução não exige rede.')


if __name__ == '__main__':
    main()
