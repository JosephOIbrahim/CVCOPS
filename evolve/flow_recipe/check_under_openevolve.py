"""Run the evaluator through OpenEvolve's own Evaluator and config loader. Makes no model calls."""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    import openevolve
    from openevolve.config import load_config
    from openevolve.evaluator import Evaluator

    cfg = load_config(os.path.join(HERE, "config.yaml"))
    print("openevolve", openevolve.__version__)
    print("config ok | iterations", cfg.max_iterations, "| enforce_evolve_blocks", cfg.enforce_evolve_blocks,
          "| parallel_evaluations", cfg.evaluator.parallel_evaluations, "| cascade", cfg.evaluator.cascade_evaluation,
          cfg.evaluator.cascade_thresholds, "| features", cfg.database.feature_dimensions,
          "| models", [(m.name, m.weight) for m in cfg.llm.models], "| api_base", cfg.llm.api_base)

    ev = Evaluator(cfg.evaluator, os.path.join(HERE, "evaluator.py"))
    seed = open(os.path.join(HERE, "initial_program.py")).read()
    m = asyncio.run(ev.evaluate_program(seed, program_id="seed"))
    print("seed   ->", {k: round(v, 3) for k, v in m.items() if isinstance(v, (int, float))})
    print("        artifacts:", ev.get_pending_artifacts("seed"))

    cheat = seed.replace("    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)\n    return dis.calc(a, b, None)",
                         "    return cv2.blur(cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST).calc(a, b, None), (151, 151))")
    assert cheat != seed
    m = asyncio.run(ev.evaluate_program(cheat, program_id="cheat"))
    print("cheat  ->", {k: round(v, 3) for k, v in m.items() if isinstance(v, (int, float))})
    print("        artifacts:", str(ev.get_pending_artifacts("cheat"))[:230])

    fast = seed.replace("PRESET_MEDIUM", "PRESET_FAST")
    m = asyncio.run(ev.evaluate_program(fast, program_id="fast"))
    print("FAST   ->", {k: round(v, 3) for k, v in m.items() if isinstance(v, (int, float))})

if __name__ == "__main__":     # required on Windows/macOS: multiprocessing uses spawn
    main()
