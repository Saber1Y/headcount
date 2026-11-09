// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Script, console} from "forge-std/Script.sol";
import {HeadcountRegistry} from "../src/HeadcountRegistry.sol";

/// Deploy with a Foundry keystore account, never a raw key on the command line:
///   forge script script/Deploy.s.sol --rpc-url liteforge --account <name> --broadcast
/// HEADCOUNT_OWNER sets the publishing owner; it defaults to the deployer.
contract Deploy is Script {
    function run() external returns (HeadcountRegistry registry) {
        vm.startBroadcast();
        address owner = vm.envOr("HEADCOUNT_OWNER", msg.sender);
        registry = new HeadcountRegistry(owner);
        vm.stopBroadcast();
        console.log("HeadcountRegistry", address(registry));
        console.log("owner", owner);
    }
}
