from __future__ import annotations

from functools import reduce
import os
import sys
import argparse
from typing import Any

from aeon.backend.evaluator import EvaluationContext
from aeon.backend.evaluator import eval
from aeon.core.types import top
from aeon.core.bind import bind_ids
from aeon.sugar.bind import bind
from aeon.decorators import Metadata
from aeon.frontend.anf_converter import ensure_anf
from aeon.frontend.parser import parse_term
from aeon.logger.logger import export_log
from aeon.logger.logger import setup_logger
from aeon.prelude.prelude import evaluation_vars
from aeon.prelude.prelude import typing_vars
from aeon.sugar.ast_helpers import st_top
from aeon.sugar.desugar import DesugaredProgram, desugar
from aeon.sugar.lowering import lower_to_core, lower_to_core_context, type_to_core
from aeon.sugar.parser import parse_program
from aeon.sugar.program import Program, STerm
from aeon.synthesis.uis.api import SynthesisUI
from aeon.synthesis.uis.ncurses import NCursesUI
from aeon.synthesis.uis.terminal import TerminalUI
from aeon.synthesis_grammar.identification import incomplete_functions_and_holes
from aeon.synthesis_grammar.synthesizer import synthesize, parse_config
from aeon.elaboration import UnificationException, elaborate
from aeon.utils.ctx_helpers import build_context
from aeon.utils.time_utils import RecordTime
from aeon.typechecking import check_type_errors
from aeon.utils.name import Name

from aeon.synthesis_grammar.synthesizer import SynthesisError

sys.setrecursionlimit(10000)


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("filename", help="name of the aeon files to be synthesized")
    parser.add_argument("--core", action="store_true", help="synthesize a aeon core file")

    parser.add_argument(
        "-l",
        "--log",
        nargs="+",
        default="",
        help="""set log level: \nTRACE \nDEBUG \nINFO \nWARNINGS \nCONSTRAINT \nTYPECHECKER \nSYNTH_TYPE \nCONSTRAINT \nSYNTHESIZER
                \nERROR \nCRITICAL\n TIME""",
    )
    parser.add_argument(
        "-f",
        "--logfile",
        action="store_true",
        help="export log file",
    )

    parser.add_argument(
        "-csv",
        "--csv-synth",
        action="store_true",
        help="export synthesis csv file",
    )

    parser.add_argument(
        "-gp",
        "--gp-config",
        help="path to the GP configuration file",
    )

    parser.add_argument(
        "-csec",
        "--config-section",
        help="section name in the GP configuration file",
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show debug information",
    )

    parser.add_argument(
        "-t",
        "--timings",
        action="store_true",
        help="Show timing information",
    )

    parser.add_argument(
        "-rg",
        "--refined-grammar",
        action="store_true",
        help="Use the refined grammar for synthesis",
    )

    parser.add_argument("-n", "--no-main", action="store_true", help="Disables introducing hole in main")

    return parser.parse_args()


def read_file(filename: str) -> str:
    with open(filename) as file:
        return file.read()


def log_type_errors(errors: list[Exception | str]):
    print("TYPECHECKER", "-------------------------------")
    print("TYPECHECKER", "+     Type Checking Error     +")
    for error in errors:
        print("TYPECHECKER", "-------------------------------")
        print("TYPECHECKER", error)
    print("TYPECHECKER", "-------------------------------")


def select_synthesis_ui() -> SynthesisUI:
    if os.environ.get("TERM", None):
        return NCursesUI()
    else:
        return TerminalUI()


def main() -> None:
    args = parse_arguments()
    logger = setup_logger()
    export_log(args.log, args.logfile, args.filename)
    if args.debug:
        logger.add(sys.stderr)
    if args.timings:
        logger.add(sys.stderr, level="TIME")

    aeon_code = read_file(args.filename)

    if args.core:
        with RecordTime("ParseCore"):
            # TODO: Remove old version
            # core_typing_vars = {k: type_to_core(typing_vars[k]) for k in typing_vars}

            core_typing_vars: dict[Name, Any] = reduce(
                lambda acc, el: acc | {el[0]: type_to_core(el[1], available_vars=[e for e in acc.items()])},
                typing_vars.items(),
                {},
            )

            typing_ctx = build_context(core_typing_vars)
            core_ast = parse_term(aeon_code)
            metadata: Metadata = {}
    else:
        with RecordTime("ParseSugar"):
            prog: Program = parse_program(aeon_code)

        with RecordTime("Desugar"):
            desugared: DesugaredProgram = desugar(prog, is_main_hole=not args.no_main)

        with RecordTime("Bind"):
            ctx, progt = bind(desugared.elabcontext, desugared.program)
            desugared = DesugaredProgram(progt, ctx, desugared.metadata)
            metadata = desugared.metadata

        try:
            with RecordTime("Elaboration"):
                sterm: STerm = elaborate(desugared.elabcontext, desugared.program, st_top)
        except UnificationException as e:
            log_type_errors([e])
            sys.exit(1)

        with RecordTime("Core generation"):
            typing_ctx = lower_to_core_context(desugared.elabcontext)
            core_ast = lower_to_core(sterm)
            typing_ctx, core_ast = bind_ids(typing_ctx, core_ast)
            logger.debug(core_ast)

    with RecordTime("ANF conversion"):
        core_ast_anf = ensure_anf(core_ast)
        logger.debug(core_ast_anf)

    with RecordTime("TypeChecking"):
        type_errors = check_type_errors(typing_ctx, core_ast_anf, top)
    if type_errors:
        log_type_errors(type_errors)
        sys.exit(1)

    with RecordTime("Preparing execution env"):
        evaluation_ctx = EvaluationContext(evaluation_vars)

    with RecordTime("DetectSynthesis"):
        incomplete_functions: list[
            tuple[
                Name,
                list[Name],
            ]
        ] = incomplete_functions_and_holes(
            typing_ctx,
            core_ast_anf,
        )

    if incomplete_functions:
        filename = args.filename if args.csv_synth else None
        with RecordTime("ParseConfig"):
            synth_config = (
                parse_config(args.gp_config, args.config_section) if args.gp_config and args.config_section else None
            )

        ui = select_synthesis_ui()

        with RecordTime("Synthesis"):
            try:
                program, terms = synthesize(
                    typing_ctx,
                    evaluation_ctx,
                    core_ast_anf,
                    incomplete_functions,
                    metadata,
                    filename,
                    synth_config,
                    args.refined_grammar,
                    ui,
                )
                ui.display_results(program, terms)
            except SynthesisError as e:
                print("SYNTHESIZER", "-------------------------------")
                print("SYNTHESIZER", "+     Synthesis Error     +")
                print("SYNTHESIZER", e)
                print("SYNTHESIZER", "-------------------------------")
                sys.exit(1)
        sys.exit(0)
    with RecordTime("Evaluation"):
        eval(core_ast, evaluation_ctx)


if __name__ == "__main__":
    main()
