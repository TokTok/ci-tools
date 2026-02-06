/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright © 2025-2026 The TokTok team.
 */
#include <QApplication>
#include <QCommandLineParser>

int main(int argc, char* argv[])
{
    QApplication a(argc, argv);

    QCommandLineParser parser;
    parser.setApplicationDescription(QStringLiteral("CiTools"));
    parser.addHelpOption();
    parser.addVersionOption();
    parser.process(a);

    return QApplication::exec();
}
