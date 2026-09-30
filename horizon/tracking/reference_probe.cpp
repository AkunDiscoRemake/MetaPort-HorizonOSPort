// Host-only independent structural check using flatc-generated public schema.
// This does NOT link ExecuTorch, load delegates, or invoke model methods.
#include "program_generated.h"
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  std::ifstream file(argv[1], std::ios::binary | std::ios::ate);
  if (!file) return 2;
  const auto size = file.tellg();
  if (size < 64 || size > 64 * 1024 * 1024) return 2;
  std::vector<uint8_t> bytes(static_cast<size_t>(size));
  file.seekg(0);
  if (!file.read(reinterpret_cast<char*>(bytes.data()), size)) return 2;
  // Restrict metadata verification to the eh00 program region, not its weights.
  if (std::string(reinterpret_cast<char*>(bytes.data() + 8), 4) != "eh00") return 2;
  const auto program_size = flatbuffers::ReadScalar<uint64_t>(bytes.data() + 16);
  if (program_size < 32 || program_size > bytes.size()) return 2;
  flatbuffers::Verifier verifier(bytes.data(), static_cast<size_t>(program_size), 64, 100000);
  const bool verified = executorch_flatbuffer::VerifyProgramBuffer(verifier);
  std::cout << "{\"public_schema_verifier_passed\":" << (verified ? "true" : "false")
            << ",\"model_executed\":false,\"int_getters\":{";
  bool first = true;
  if (verified) {
    const auto* plans = executorch_flatbuffer::GetProgram(bytes.data())->execution_plan();
    if (plans && plans->size() <= 128) for (const auto* plan : *plans) {
      if (!plan->name() || plan->name()->size() > 128) continue;
      const auto name = plan->name()->str();
      // Fixed names only: no firmware-controlled JSON escaping or arbitrary dumps.
      if (name != "num_layers" && name != "kernel_size" && name != "hidden_dim" &&
          name != "left_context" && name != "featurizer_version") continue;
      if ((plan->inputs() && plan->inputs()->size()) ||
          (plan->delegates() && plan->delegates()->size())) continue;
      bool executable = false;
      if (plan->chains()) for (const auto* chain : *plan->chains()) {
        if (chain->instructions() && chain->instructions()->size()) executable = true;
      }
      if (executable || !plan->outputs() || plan->outputs()->size() != 1 || !plan->values()) continue;
      const int index = plan->outputs()->Get(0);
      if (index < 0 || static_cast<unsigned>(index) >= plan->values()->size()) continue;
      const auto* scalar = plan->values()->Get(index)->val_as_Int();
      if (!scalar) continue;
      if (!first) std::cout << ',';
      first = false;
      std::cout << '"' << name << "\":" << scalar->int_val();
    }
  }
  std::cout << "}}\n";
}
