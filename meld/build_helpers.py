# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Copied and adapted from the DistUtilsExtra project
# Created by Sebastian Heinlein and Martin Pitt
# Copyright Canonical Ltd.

# Modified by Kai Willadsen for the Meld project
# Copyright (C) 2013-2014 Kai Willadsen <kai.willadsen@gmail.com>

from __future__ import print_function

import distutils.cmd
import distutils.command.build
import distutils.command.install_data
import distutils.dir_util
import glob
import os.path


class build_extra(distutils.command.build.build):

    def __init__(self, dist):
        distutils.command.build.build.__init__(self, dist)

        def has_help(command):
            return "build_help" in self.distribution.cmdclass

        def has_icons(command):
            return "build_icons" in self.distribution.cmdclass

        def has_i18n(command):
            return "build_i18n" in self.distribution.cmdclass

        def has_data(command):
            return "build_data" in self.distribution.cmdclass

        self.sub_commands.append(("build_i18n", has_i18n))
        self.sub_commands.append(("build_icons", has_icons))
        self.sub_commands.append(("build_help", has_help))
        self.sub_commands.append(("build_data", has_data))


class build_data(distutils.cmd.Command):

    gschemas = [
        ('share/glib-2.0/schemas/', ['data/org.gnome.meld.gschema.xml'])
    ]

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def get_data_files(self):
        return self.gschemas

    def run(self):
        data_files = self.distribution.data_files
        data_files.extend(self.get_data_files())


class build_help(distutils.cmd.Command):

    help_dir = 'help'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def get_data_files(self):
        data_files = []
        name = self.distribution.metadata.name

        if "LINGUAS" in os.environ:
            self.selected_languages = os.environ["LINGUAS"].split()
        else:
            self.selected_languages = os.listdir(self.help_dir)

        self.C_PAGES = glob.glob(os.path.join(self.help_dir, 'C', '*.page'))
        self.C_EXTRA = glob.glob(os.path.join(self.help_dir, 'C', '*.xml'))

        for lang in self.selected_languages:
            source_path = os.path.join(self.help_dir, lang)
            if not os.path.exists(source_path):
                continue

            build_path = os.path.join('build', self.help_dir, lang)
            if not os.path.exists(build_path):
                os.makedirs(build_path)

            if lang != 'C':
                po_file = os.path.join(source_path, lang + '.po')
                mo_file = os.path.join(build_path, lang + '.mo')

                msgfmt = ['msgfmt', po_file, '-o', mo_file]
                self.spawn(msgfmt)
                for page in self.C_PAGES:
                    itstool = ['itstool', '-m', mo_file, '-o', build_path, page]
                    self.spawn(itstool)
                for extra in self.C_EXTRA:
                    extra_path = os.path.join(build_path, os.path.basename(extra))
                    if os.path.exists(extra_path):
                        os.unlink(extra_path)
                    os.symlink(os.path.relpath(extra, source_path), extra_path)
            else:
                distutils.dir_util.copy_tree(source_path, build_path)

            xml_files = glob.glob('%s/*.xml' % build_path)
            mallard_files = glob.glob('%s/*.page' % build_path)
            path_help = os.path.join('share', 'help', lang, name)
            path_figures = os.path.join(path_help, 'figures')
            data_files.append((path_help, xml_files + mallard_files))
            data_files.append((path_figures, glob.glob('%s/figures/*.png' % build_path)))

        return data_files

    def run(self):
        data_files = self.distribution.data_files
        data_files.extend(self.get_data_files())
        self.check_help()

    def check_help(self):
        for lang in self.selected_languages:
            build_path = os.path.join('build', self.help_dir, lang)
            if not os.path.exists(build_path):
                continue

            pages = [os.path.basename(p) for p in self.C_PAGES]
            for page in pages:
                page_path = os.path.join(build_path, page)
                if not os.path.exists(page_path):
                    print("Skipping missing file", page_path)
                    continue
                lint = ['xmllint', '--noout', '--noent', '--path', build_path,
                        '--xinclude', page_path]
                self.spawn(lint)


class build_icons(distutils.cmd.Command):

    icon_dir = os.path.join("data", "icons")

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        data_files = self.distribution.data_files

        for theme in glob.glob(os.path.join(self.icon_dir, "*")):
            for size in glob.glob(os.path.join(theme, "*")):
                for category in glob.glob(os.path.join(size, "*")):
                    icons = (glob.glob(os.path.join(category, "*.png")) +
                             glob.glob(os.path.join(category, "*.svg")))
                    icons = [icon for icon in icons if not os.path.islink(icon)]
                    if not icons:
                        continue
                    data_files.append(("share/icons/%s/%s/%s" %
                                       (os.path.basename(theme),
                                        os.path.basename(size),
                                        os.path.basename(category)),
                                       icons))


class build_i18n(distutils.cmd.Command):

    bug_contact = None
    domain = "meld"
    po_dir = "po"
    merge_po = False

    # FIXME: It's ridiculous to specify these here, but I know of no other
    # way except magically extracting them from self.distribution.data_files
    desktop_files = [('share/applications', glob.glob("data/*.desktop.in"))]
    xml_files = [
        ('share/appdata', glob.glob("data/*.appdata.xml.in")),
        ('share/mime/packages', glob.glob("data/mime/*.xml.in"))
    ]
    schemas_files = []
    key_files = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def _rebuild_po(self):
        # If there is a po/LINGUAS file, or the LINGUAS environment variable
        # is set, only compile the languages listed there.
        selected_languages = None
        linguas_file = os.path.join(self.po_dir, "LINGUAS")
        if "LINGUAS" in os.environ:
            selected_languages = os.environ["LINGUAS"].split()
        elif os.path.isfile(linguas_file):
            selected_languages = open(linguas_file).read().split()

        # Update po(t) files and print a report
        # We have to change the working dir to the po dir for intltool
        cmd = ["intltool-update", (self.merge_po and "-r" or "-p"), "-g", self.domain]
        wd = os.getcwd()
        os.chdir(self.po_dir)
        self.spawn(cmd)
        os.chdir(wd)
        max_po_mtime = 0
        for po_file in glob.glob("%s/*.po" % self.po_dir):
            lang = os.path.basename(po_file[:-3])
            if selected_languages and not lang in selected_languages:
                continue
            mo_dir = os.path.join("build", "mo", lang, "LC_MESSAGES")
            mo_file = os.path.join(mo_dir, "%s.mo" % self.domain)
            if not os.path.exists(mo_dir):
                os.makedirs(mo_dir)
            cmd = ["msgfmt", po_file, "-o", mo_file]
            po_mtime = os.path.getmtime(po_file)
            mo_mtime = os.path.exists(mo_file) and os.path.getmtime(mo_file) or 0
            if po_mtime > max_po_mtime:
                max_po_mtime = po_mtime
            if po_mtime > mo_mtime:
                self.spawn(cmd)

            targetpath = os.path.join("share/locale", lang, "LC_MESSAGES")
            self.distribution.data_files.append((targetpath, (mo_file,)))
        self.max_po_mtime = max_po_mtime

    def run(self):
        if self.bug_contact is not None:
            os.environ["XGETTEXT_ARGS"] = "--msgid-bugs-address=%s " % \
                                          self.bug_contact

        self._rebuild_po()

        intltool_switches = [
            (self.xml_files, "-x"),
            (self.desktop_files, "-d"),
            (self.schemas_files, "-s"),
            (self.key_files, "-k"),
        ]

        for file_set, switch in intltool_switches:
            for target, files in file_set:
                build_target = os.path.join("build", target)
                if not os.path.exists(build_target):
                    os.makedirs(build_target)
                files_merged = []
                for file in files:
                    file_merged = os.path.basename(file)
                    if file_merged.endswith(".in"):
                        file_merged = file_merged[:-3]
                    file_merged = os.path.join(build_target, file_merged)
                    cmd = ["intltool-merge", switch, self.po_dir, file,
                           file_merged]
                    mtime_merged = (os.path.exists(file_merged) and
                                    os.path.getmtime(file_merged) or 0)
                    mtime_file = os.path.getmtime(file)
                    if mtime_merged < self.max_po_mtime or mtime_merged < mtime_file:
                        # Only build if output is older than input (.po,.in)
                        self.spawn(cmd)
                    files_merged.append(file_merged)
                self.distribution.data_files.append((target, files_merged))


class install_data(distutils.command.install_data.install_data):

    user_options = [
        ("no-compile-schemas", None,
         "Don't compile gsettings schemas post-install"),
    ]
    boolean_options = ["no-compile-schemas"]

    def initialize_options(self):
        distutils.command.install_data.install_data.initialize_options(self)
        self.no_compile_schemas = None

    def finalize_options(self):
        distutils.command.install_data.install_data.finalize_options(self)
        if self.no_compile_schemas is None:
            self.no_compile_schemas = bool(
                os.environ.get('NO_COMPILE_SCHEMAS', None))

    def run(self):
        distutils.command.install_data.install_data.run(self)
        if not self.no_compile_schemas:
            gschema_path = build_data.gschemas[0][0]
            gschema_install = os.path.join(self.install_dir, gschema_path)
            self.spawn(["glib-compile-schemas", gschema_install])