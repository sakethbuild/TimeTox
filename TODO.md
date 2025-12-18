# TimeTox Project - To-Do List

## Priority Tasks

### High Priority

- [ ] **Check new judge output with PDF input**
  - Verify Stage 3 judge behavior when given direct PDF access
  - Compare judge corrections vs ground truth
  - Document error patterns the judge catches/misses

- [ ] **Save vanilla run results for comparison (clean for paper production)**
  - Run `core/test_extraction.py` on all 20 synthetic schedules
  - Save results to `results/vanilla_baseline_YYYY-MM-DD.json`
  - Generate clean tables for paper appendix

### Medium Priority

- [ ] Run full 20-schedule evaluation with best pipeline (Split Windows)
  - Expand from 5-PDF test to full dataset
  - Track per-complexity accuracy (simple/moderate/complex)
  - Document edge cases and failure modes

- [ ] Document final pipeline architecture for paper
  - Create architecture diagram (mermaid or figure)
  - Write methods section describing the approach
  - Prepare accuracy/comparison tables

### Low Priority

- [ ] Investigate Chain-of-Thought performance drop
  - Why does explicit enumeration hurt accuracy?
  - Consider hybrid approaches

- [ ] Explore temperature optimization per-window
  - Different temps for screening vs 12-month counts?

- [ ] Add real protocol testing
  - Test on `ExampleSoA1.pdf` and `ExampleSoA2.pdf`
  - Document any domain adaptation needed

---

## Completed Tasks

- [x] Implement multi-agent comparison framework
- [x] Test 5 different extraction architectures
- [x] Implement three-stage pipeline with judge
- [x] Optimize temperature sweep with parallelization
- [x] Reorganize project directory structure
- [x] Create session documentation

---

## Notes

### Best Performing Configuration
- **Architecture**: Split Windows
- **Temperature**: 0.1
- **Model**: gemini-3-flash-preview
- **Results**: 51.7% exact, 90.0% clinical accuracy

### File Locations
- Core pipelines: `core/`
- Experiments: `experiments/`
- Results: `results/`
- Documentation: `docs/`
- Test data: `synthetic_schedules/`

